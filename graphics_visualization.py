import weakref
import math
import logging
import random
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, qAbs
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QStyle

from simulation_model import SimObject, Train, Signal, Junction

log = logging.getLogger('graphics_visualization')


class QtEdge(QGraphicsItem):
    item_type = QGraphicsItem.UserType + 2

    def __init__(self, source_node: 'QtNode', dest_node: 'QtNode'):
        super().__init__()

        self._source_point = QPointF()
        self._dest_point = QPointF()
        self.bounds = QRectF()
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.source: weakref.ReferenceType[QtNode] = weakref.ref(source_node)
        self.dest: weakref.ReferenceType[QtNode] = weakref.ref(dest_node)
        self.source().add_edge(self)
        self.dest().add_edge(self)
        self.adjust()

    def source_node(self) -> weakref.ReferenceType['QtNode']:
        return self.source()

    def set_source_node(self, node: 'QtNode'):
        self.source = weakref.ref(node)
        self.adjust()

    def dest_node(self) -> weakref.ReferenceType['QtNode']:
        return self.dest()

    def set_dest_node(self, node: 'QtNode'):
        self.dest = weakref.ref(node)
        self.adjust()

    def adjust(self):
        if not self.source() or not self.dest():
            log.warning(f'No source ({self.source()}) or dest ({self.dest()}) node to adjust')
            return

        line = QLineF(self.mapFromItem(self.source(), 0, 0), self.mapFromItem(self.dest(), 0, 0))
        length = line.length()

        if length == 0.0:
            return

        edge_offset = QPointF((line.dx() * 10) / length, (line.dy() * 10) / length)

        self.prepareGeometryChange()
        self._source_point = line.p1() + edge_offset
        self._dest_point = line.p2() - edge_offset

    def boundingRect(self):
        return self.bounds

    def paint(self, painter, option, widget):
        if not self.source() or not self.dest():
            log.warning(f'No source ({self.source()}) or dest ({self.dest()}) node. Nothing to paint')
            return

        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        line = QLineF(self._source_point, self._dest_point)
        painter.drawLine(line)
        line_bounds = QRectF(line.p1(), line.p2()).normalized()

        text = f'NONE'
        text_bounds = painter.fontMetrics().boundingRect(text)
        text_bounds.moveTo(line_bounds.center().toPoint())
        painter.drawText(text_bounds, 0, text)

        self.bounds = line_bounds.united(text_bounds)


class QtNode(QGraphicsItem):
    item_type = QGraphicsItem.UserType + 1

    def __init__(self, graph_widget: 'GraphWidget'):
        super().__init__()

        self.graph = weakref.ref(graph_widget)
        self._edge_list: List[weakref.ReferenceType[QtEdge]] = []
        self._new_pos = QPointF()
        self.bounds = QRectF()
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(-1)

    def add_edge(self, edge):
        self._edge_list.append(weakref.ref(edge))
        edge.adjust()

    def edges(self) -> List[weakref.ReferenceType[QtEdge]]:
        return self._edge_list

    def calculate_forces(self):
        if not self.scene() or self.scene().mouseGrabberItem() is self:
            self._new_pos = self.pos()
            return

        # Sum up all forces pushing this item away.
        xvel = 0.0
        yvel = 0.0
        for item in self.scene().items():
            if not isinstance(item, QtNode):
                continue

            line = QLineF(self.mapFromItem(item, 0, 0), QPointF(0, 0))
            dx = line.dx()
            dy = line.dy()
            l = 2.0 * (dx * dx + dy * dy)
            if l > 0:
                xvel += (dx * 150.0) / l
                yvel += (dy * 150.0) / l

        # Now subtract all forces pulling items together.
        weight = (len(self._edge_list) + 1) * 10.0
        for edge in self._edge_list:
            if edge().source_node() is self:
                pos = self.mapFromItem(edge().dest_node(), 0, 0)
            else:
                pos = self.mapFromItem(edge().source_node(), 0, 0)
            xvel += pos.x() / weight
            yvel += pos.y() / weight

        if qAbs(xvel) < 0.1 and qAbs(yvel) < 0.1:
            xvel = yvel = 0.0

        scene_rect = self.scene().sceneRect()
        self._new_pos = self.pos() + QPointF(xvel, yvel)
        self._new_pos.setX(min(max(self._new_pos.x(), scene_rect.left() + 10), scene_rect.right() - 10))
        self._new_pos.setY(min(max(self._new_pos.y(), scene_rect.top() + 10), scene_rect.bottom() - 10))

    def advance(self):
        if self._new_pos == self.pos():
            return False

        self.setPos(self._new_pos)
        return True

    def boundingRect(self):
        return self.bounds

    def shape(self):
        path = QPainterPath()
        path.addEllipse(-10, -10, 20, 20)
        return path

    def paint(self, painter, option, widget):
        # Basic circle
        painter.setPen(Qt.NoPen)
        if option.state & QStyle.State_Sunken:
            # Click and drag
            painter.setBrush(Qt.yellow)
        else:
            painter.setBrush(Qt.darkGray)
        ellipse_bounds = QRectF(-10, -10, 20, 20)
        painter.drawEllipse(ellipse_bounds)
        self.bounds = ellipse_bounds

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            for edge in self._edge_list:
                edge().adjust()
            self.graph().item_moved()

        return QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, event):
        self.update()
        QGraphicsItem.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.update()
        QGraphicsItem.mouseReleaseEvent(self, event)


class QtJunction(QtNode):
    def __init__(self, graph_widget: 'GraphWidget', junction: Junction):
        super().__init__(graph_widget)
        self.junction = junction
        self.fork_qt_notes: Optional[Tuple[weakref.ReferenceType['QtNode'], weakref.ReferenceType['QtNode']]] = None

    def update_fork_nodes(self):
        if self.junction.fork_connections is None:
            return

        # Find the two edges from the fork identifiers
        qt_node_fork1, qt_node_fork2 = None, None
        for qt_edge in self._edge_list:
            edge_node1: weakref.ReferenceType[QtNode] = qt_edge().source_node()
            edge_node2: weakref.ReferenceType[QtNode] = qt_edge().dest_node()
            if edge_node1.junction.ident == self.junction.fork_connections[0]:
                qt_node_fork1 = edge_node1
            if edge_node2.junction.ident == self.junction.fork_connections[1]:
                qt_node_fork2 = edge_node2
            if qt_node_fork1 is not None and qt_node_fork2 is not None:
                break
        if qt_node_fork1 is None or qt_node_fork2 is None:
            # Forks not found, no update
            return
        self.fork_qt_notes = (qt_node_fork1, qt_node_fork2)

    def add_edge(self, edge):
        super().add_edge(edge)
        # Update our fork references if we're a Junction,
        self.update_fork_nodes()

    def paint(self, painter, option, widget):
        # Draw circle
        painter.setPen(Qt.NoPen)
        if option.state & QStyle.State_Sunken:
            # Click and drag
            painter.setBrush(Qt.yellow)
        else:
            painter.setBrush(Qt.darkGray)
        ellipse_bounds = QRectF(-10, -10, 20, 20)
        painter.drawEllipse(ellipse_bounds)

        # Draw text
        text = f'Junction({self.junction.ident})'
        painter.setPen(QPen(Qt.black))
        text_bounds = painter.fontMetrics().boundingRect(text)
        text_bounds.moveTo(ellipse_bounds.center().toPoint())
        # text_bounds.setWidth(500)  # TODO: Sometimes fontMetrics.boundingRect returns an incorrect width?
        painter.drawText(text_bounds, text)

        # Draw fork
        if self.fork_qt_notes is not None:
            qt_node_fork1, qt_node_fork2 = self.fork_qt_notes
            # TODO: Need to repaint whenever forks change position
            line1 = QLineF(self.mapFromItem(qt_node_fork1, QPointF(0, 0)), QPointF(0, 0))
            line2 = QLineF(self.mapFromItem(qt_node_fork2, QPointF(0, 0)), QPointF(0, 0))
            # Lines will be cut off at the item bounds, no need to rescale them
            painter.setPen(QPen(Qt.red))
            painter.drawLine(line1)
            painter.drawLine(line2)

        # calculate item bounds
        self.bounds = ellipse_bounds.united(text_bounds)


class GraphWidget(QGraphicsView):
    def __init__(self, window_title: str, graph_data: Dict[SimObject, Dict]):
        super().__init__()

        self._timer_id = 0

        scene = QGraphicsScene(self)
        scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        scene.setSceneRect(-200, -200, 400, 400)
        self.setScene(scene)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        log.debug(f'Creating graphics representation of:\n{graph_data}')

        # First need to add all create a QtNode for every node id
        nodes: Dict[SimObject, QtNode] = {}
        for node_start_obj in graph_data.keys():
            # Convert simulation types into graphics types
            if isinstance(node_start_obj, Junction):
                node = QtJunction(self, node_start_obj)
            else:
                log.warning(f'Unknown node type: {node_start_obj}')
                node = QtNode(self)
            nodes[node_start_obj] = node

        # Then we can go through and create a QtEdge containing two QtNodes
        edges: List[QtEdge] = []
        for node_start_obj, edge_connection_dict in graph_data.items():
            for node_end_obj, edge_data in edge_connection_dict.items():
                # TODO: Figure out how to pass simulation edge data here
                edges.append(QtEdge(nodes[node_start_obj], nodes[node_end_obj]))

        # Then we add all the QtNodes and QtEdges to the scene
        for node in nodes.values():
            scene.addItem(node)
        for edge in edges:
            scene.addItem(edge)

        self.randomize_nodes()

        self.scale(0.8, 0.8)
        self.setMinimumSize(400, 400)
        self.setWindowTitle(window_title)

    def randomize_nodes(self):
        for item in self.scene().items():
            if isinstance(item, QtNode):
                item.setPos(-150 + random.randint(0, 300), -150 + random.randint(0, 300))

    def item_moved(self):
        if not self._timer_id:
            self._timer_id = self.startTimer(1000 / 25)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Plus:
            self.scale_view(1.2)
        elif key == Qt.Key_Minus:
            self.scale_view(1 / 1.2)
        elif key == Qt.Key_Space or key == Qt.Key_Enter:
            self.randomize_nodes()
        else:
            QGraphicsView.keyPressEvent(self, event)

    def timerEvent(self, event):
        nodes = [item for item in self.scene().items() if isinstance(item, QtNode)]

        for node in nodes:
            node.calculate_forces()

        items_moved = False
        for node in nodes:
            if node.advance():
                items_moved = True

        if not items_moved:
            # Stop running update calculations if nothing is moving
            self.killTimer(self._timer_id)
            self._timer_id = 0

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.scale_view(math.pow(2.0, -delta / 240.0))

    def scale_view(self, scale_factor: float):
        factor = self.transform().scale(scale_factor, scale_factor).mapRect(QRectF(0, 0, 1, 1)).width()

        if factor < 0.07 or factor > 100:
            return

        self.scale(scale_factor, scale_factor)

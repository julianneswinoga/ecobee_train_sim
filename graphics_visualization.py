import weakref
import math
import sys
import signal
import traceback
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Generator

import networkx as nx
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, qAbs, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QStyle,
    QHBoxLayout,
    QFileDialog,
    QStyleOptionGraphicsItem,
)
from pyqtgraph.parametertree import Parameter, ParameterTree, parameterTypes

from simulation_model import SimObject, Train, Track, Junction, Simulation

log = logging.getLogger('graphics_visualization')


class QtEdge(QGraphicsItem):
    item_type = QGraphicsItem.UserType + 2

    def __init__(self, source_node: 'QtNode', dest_node: 'QtNode'):
        """
        Base object for representing a graph edge
        :param source_node: Source node for the edge
        :param dest_node: Destination node for the edge
        """
        super().__init__()

        self.connecting_line = QLineF()
        self.bounds = QRectF()
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.source: weakref.ReferenceType[QtNode] = weakref.ref(source_node)
        self.dest: weakref.ReferenceType[QtNode] = weakref.ref(dest_node)
        self.source().add_edge(self)
        self.dest().add_edge(self)
        self.adjust()
        self.show_debug = False

    def adjust(self):
        """
        Update our connecting line geometry to the current source and
        destination Node positions
        """
        if not self.source() or not self.dest():
            log.warning(f'No source ({self.source()}) or dest ({self.dest()}) node to adjust')
            return

        line = QLineF(self.mapFromItem(self.source(), 0, 0), self.mapFromItem(self.dest(), 0, 0))
        length = line.length()

        if length == 0.0:
            return

        self.prepareGeometryChange()
        source_offset = self.source().circle_radius / 2
        dest_offset = self.dest().circle_radius / 2
        source_point = line.p1() + QPointF((line.dx() * source_offset) / length, (line.dy() * source_offset) / length)
        dest_point = line.p2() - QPointF((line.dx() * dest_offset) / length, (line.dy() * dest_offset) / length)
        self.connecting_line = QLineF(source_point, dest_point)

    def boundingRect(self) -> QRectF:
        """
        Return this QGraphicsItems bounding rectangle
        :return: Object bounding rectangle
        """
        return self.bounds

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        """
        Paint this QGraphicsItem
        :param painter: QPainter instance for drawing
        :param option: Styling options
        :param widget: Optionally the widget that is being painted on
        """
        if not self.source() or not self.dest():
            log.warning(f'No source ({self.source()}) or dest ({self.dest()}) node. Nothing to paint')
            return

        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(self.connecting_line)
        line_bounds = QRectF(self.connecting_line.p1(), self.connecting_line.p2()).normalized()

        self.bounds = line_bounds


class QtTrain(QGraphicsItem):
    def __init__(self, train_colour: Qt.GlobalColor, parent: QtEdge):
        """
        QGraphicsItem representing a Train. Must be a child of an Edge
        :param train_colour: Colour of the Train
        :param parent: Edge parent that the train currently resides on
        """
        super().__init__(parent)
        self.train_colour: Qt.GlobalColor = train_colour
        self.bounds = QRectF()
        self.show_debug = False

    def boundingRect(self) -> QRectF:
        """
        Return this QGraphicsItems bounding rectangle
        :return: Object bounding rectangle
        """
        return self.bounds

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        """
        Paint this QGraphicsItem
        :param painter: QPainter instance for drawing
        :param option: Styling options
        :param widget: Optionally the widget that is being painted on
        """
        parent_item: QtTrack = self.parentItem()
        parent_center = parent_item.connecting_line.center()
        body_rect = QRectF(parent_center.x(), parent_center.y(), 30, 10)
        body_rect.moveCenter(body_rect.topLeft())  # Center the rectangle on the line
        front_rect = QRectF(body_rect.x(), body_rect.y(), 5, 10)

        facing_sim_junction = parent_item.track.train.facing_junction
        if parent_item.source().junction == facing_sim_junction:
            facing_qt_junction = parent_item.source()
        elif parent_item.dest().junction == facing_sim_junction:
            facing_qt_junction = parent_item.dest()
        else:
            raise IndexError(f'No facing junction for {parent_item.track.train}')

        # Rotate ourself about the center
        # (can't just rotate the painting because the bounds will get screwed up)
        self.resetTransform()
        t = self.transform()
        t.translate(body_rect.center().x(), body_rect.center().y())
        # I hate rotation matrices, this took a lot of trial and error
        line_to_facing_junction = QLineF(body_rect.center(), self.mapFromItem(facing_qt_junction, 0, 0))
        t.rotate(-line_to_facing_junction.angle() + 180)
        t.translate(-body_rect.center().x(), -body_rect.center().y())
        self.setTransform(t)

        painter.setPen(self.train_colour)
        painter.drawRect(body_rect)
        painter.setBrush(self.train_colour)
        painter.drawRect(front_rect)

        if self.show_debug:
            font = painter.font()
            text = f'Train{parent_item.track.train.ident}'
            font.setPointSize(6)
            painter.setFont(font)
            text_bounds = painter.fontMetrics().boundingRect(text)
            text_bounds.moveTo(parent_center.toPoint())
            painter.drawText(text_bounds, 0, text)
        else:
            text_bounds = QRectF()

        # Increase bounds a bit, else some minor artefact show
        siz = body_rect.size()
        siz *= 1.5
        body_rect.setSize(siz)
        self.bounds = body_rect.united(text_bounds).united(front_rect)


def random_qcolor_generator(seed: int = 0) -> Generator[QColor, None, None]:
    """
    Generator that produces random QColors (but the same colours every time it is started)
    :param seed: Optional seed for the PRNG
    :return: Random QColor
    """
    r = random.Random(seed)  # Create prng generator with a constant seed
    while True:
        yield QColor.fromRgbF(r.random(), r.random(), r.random(), 1.0)


# Start the colour generator
random_qcolor_generator = random_qcolor_generator()
track_line_colour_lookup: Dict[int, QColor] = {}


def get_track_line_colour(track_line: Train) -> QColor:
    """
    Deterministically determine the colour of a Train
    :param track_line: Train to determine the colour of
    :return: track_lines colour
    """
    global track_line_colour_lookup
    train_ident = track_line.ident
    if train_ident not in track_line_colour_lookup:
        track_line_colour_lookup[train_ident] = next(random_qcolor_generator)
        log.debug(f'Created train colour {track_line_colour_lookup[train_ident]}')
    return track_line_colour_lookup[train_ident]


class QtTrack(QtEdge):
    def __init__(self, source_junction: 'QtNode', dest_junction: 'QtNode', track: Track):
        """
        Superclass of base edge that represents a Track
        :param source_junction: Source node
        :param dest_junction: Destination node
        :param track: Simulation Track object that this is representing
        """
        super().__init__(source_junction, dest_junction)

        self.track = track
        self.qt_train: Optional[QtTrain] = None

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        """
        Paint this QGraphicsItem
        :param painter: QPainter instance for drawing
        :param option: Styling options
        :param widget: Optionally the widget that is being painted on
        """
        if not self.source() or not self.dest():
            log.warning(f'No source ({self.source()}) or dest ({self.dest()}) node. Nothing to paint')
            return

        # Draw the main connecting line (black line between nodes)
        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(self.connecting_line)
        line_bounds = QRectF(self.connecting_line.p1(), self.connecting_line.p2()).normalized()

        # Draw the train routes
        track_line_bounds = []
        connecting_line_unit_normal = self.connecting_line.unitVector().normalVector()
        for i, train_line in enumerate(self.track.trains_routed_along_track, start=1):
            # Create copy of normal line
            offset_line = QLineF(connecting_line_unit_normal.p1(), connecting_line_unit_normal.p2())
            offset_line.setLength(i * 1.0)  # normal offset increases with more track routes
            track_line_bounds.append(QRectF(offset_line.p1(), offset_line.p2()).normalized())
            offset_line_delta_point = QPointF(offset_line.dx(), offset_line.dy())

            # Create copy of connecting line
            track_line = QLineF(self.connecting_line.p1(), self.connecting_line.p2())
            # Translate it by the offset line delta
            track_line.translate(offset_line_delta_point)
            track_colour = get_track_line_colour(train_line)
            painter.setPen(QPen(track_colour, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(track_line)
            track_line_bounds.append(QRectF(track_line.p1(), track_line.p2()).normalized())

        # Create/delete a child train item if needed
        if self.track.train and not self.qt_train:
            self.qt_train = QtTrain(get_track_line_colour(self.track.train), parent=self)
            log.debug(f'Created QtTrain at {self.track}')
        elif not self.track.train and self.qt_train:
            log.debug(f'Deleting QtTrain from {self.track}')
            self.qt_train.setParentItem(None)
            del self.qt_train
            self.qt_train = None

        font = painter.font()

        # Draw any signals
        signal_ellipse_bounds = []
        for train_signal in self.track.train_signals:
            signal_sim_junction = train_signal.attached_junction
            # connecting_line is always from source to dest, so we cheat a bit to not
            # have to figure out the geomerty from scratch again
            if self.source().junction == signal_sim_junction:
                signal_point = self.connecting_line.p1()
            elif self.dest().junction == signal_sim_junction:
                signal_point = self.connecting_line.p2()
            else:
                raise IndexError(f'No attached junction for {train_signal}')
            signal_ellipse_bound = QRectF(-4, -4, 4, 4)
            signal_ellipse_bound.moveCenter(signal_point)
            signal_colour = Qt.green if train_signal.signal_state else Qt.red
            painter.setPen(signal_colour)
            painter.setBrush(signal_colour)
            painter.drawEllipse(signal_ellipse_bound)
            signal_ellipse_bounds.append(signal_ellipse_bound)

            # Signal text
            if self.show_debug:
                text = f'Sig{train_signal.ident}'
                font.setPointSize(5)
                painter.setFont(font)
                painter.setPen(Qt.black)
                text_bounds = painter.fontMetrics().boundingRect(text)
                text_bounds.moveTo(signal_ellipse_bound.center().toPoint())
                painter.drawText(text_bounds, 0, text)
                signal_ellipse_bounds.append(text_bounds)

        # Draw text
        if self.show_debug:
            text = f'Track({self.track.ident})'
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(Qt.black)
            text_bounds = painter.fontMetrics().boundingRect(text)
            text_bounds.moveTo(line_bounds.center().toPoint())
            painter.drawText(text_bounds, 0, text)
        else:
            text_bounds = QRectF()

        total_bounds = line_bounds.united(text_bounds)
        for track_line_bound in track_line_bounds:
            total_bounds = total_bounds.united(track_line_bound)
        for signal_ellipse_bound in signal_ellipse_bounds:
            total_bounds = total_bounds.united(signal_ellipse_bound)
        self.bounds = total_bounds


class QtNode(QGraphicsItem):
    item_type = QGraphicsItem.UserType + 1

    def __init__(self, graph_widget: 'GraphWidget'):
        """
        Base object for representing a graph node
        :param graph_widget: Widget representing the entire graph
        """
        super().__init__()

        self.graph = weakref.ref(graph_widget)
        self._edge_list: List[weakref.ReferenceType[QtEdge]] = []
        self._new_pos = QPointF()
        self.bounds = QRectF()
        self.circle_radius = 20
        self.circle_bounds = QRectF(
            -self.circle_radius / 2, -self.circle_radius / 2, self.circle_radius, self.circle_radius
        )
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setZValue(-1)
        self.show_debug = False

    def add_edge(self, edge: QtEdge):
        """
        Add an edge to this node
        :param edge: Edge to add
        """
        self._edge_list.append(weakref.ref(edge))
        edge.adjust()

    def calculate_forces(self):
        """
        Calculate all the forces acting on this node
        """
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
            if edge().source() is self:
                pos = self.mapFromItem(edge().dest(), 0, 0)
            else:
                pos = self.mapFromItem(edge().source(), 0, 0)
            xvel += pos.x() / weight
            yvel += pos.y() / weight

        if qAbs(xvel) < 0.1 and qAbs(yvel) < 0.1:
            xvel = yvel = 0.0

        scene_rect = self.scene().sceneRect()
        self._new_pos = self.pos() + QPointF(xvel, yvel)
        radius_offset = self.circle_radius / 2
        self._new_pos.setX(
            min(max(self._new_pos.x(), scene_rect.left() + radius_offset), scene_rect.right() - radius_offset)
        )
        self._new_pos.setY(
            min(max(self._new_pos.y(), scene_rect.top() + radius_offset), scene_rect.bottom() - radius_offset)
        )

    def advance(self, phase: int = 0) -> bool:
        """
        Set our new position from our latest calculation
        :param phase: Optional phase number for animation
        :return: True if our position changed, else False
        """
        if self._new_pos == self.pos():
            return False

        self.setPos(self._new_pos)
        return True

    def boundingRect(self) -> QRectF:
        """
        Return this QGraphicsItems bounding rectangle
        :return: Object bounding rectangle
        """
        return self.bounds

    def shape(self) -> QPainterPath:
        """
        Get the shape of this QGraphicsItem
        :return: Shape of this QGraphicsItem
        """
        path = QPainterPath()
        path.addEllipse(self.circle_bounds)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        """
        Paint this QGraphicsItem
        :param painter: QPainter instance for drawing
        :param option: Styling options
        :param widget: Optionally the widget that is being painted on
        """
        # Basic circle
        painter.setPen(Qt.NoPen)
        if option.state & QStyle.State_Sunken:
            # Click and drag
            painter.setBrush(Qt.yellow)
        else:
            painter.setBrush(Qt.darkGray)
        painter.drawEllipse(self.circle_bounds)
        self.bounds = self.circle_bounds

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """
        Called to notify that some part of the item's state has changed
        :param change: Type of change
        :param value: The new value
        :return: Parent itemChange implementation
        """
        if change == QGraphicsItem.ItemPositionChange:
            for edge in self._edge_list:
                edge().adjust()
            self.graph().item_moved()

        return QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, event):
        """
        Called when the mouse presses this QGraphicsItem
        :param event: The type of mouse event
        """
        self.update()
        QGraphicsItem.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """
        Called when the mouse releases this QGraphicsItem
        :param event: The type of mouse event
        """
        self.update()
        QGraphicsItem.mouseReleaseEvent(self, event)


class QtJunction(QtNode):
    def __init__(self, graph_widget: 'GraphWidget', junction: Junction):
        """
        Superclass of base node that represents a Junction
        :param graph_widget: Widget representing the entire graph
        :param junction: Simulation Junction object that this is representing
        """
        super().__init__(graph_widget)
        self.junction = junction
        self.fork_qt_notes: Optional[Tuple[weakref.ReferenceType['QtNode'], weakref.ReferenceType['QtNode']]] = None

    def update_fork_nodes(self):
        """
        Update our representation of which nodes the forks are connecting
        """
        # Find the two edges from the fork identifiers
        qt_node_forks = []
        for qt_edge in self._edge_list:
            edge_node1: weakref.ReferenceType[QtNode] = qt_edge().source()
            edge_node2: weakref.ReferenceType[QtNode] = qt_edge().dest()
            switch_junct1, switch_junct2 = self.junction.get_switch_state()
            # forks could be the same, can't use elif or compact into a single if
            if edge_node1.junction == switch_junct1:
                qt_node_forks.append(edge_node1)
            if edge_node1.junction == switch_junct2:
                qt_node_forks.append(edge_node1)
            if edge_node2.junction == switch_junct1:
                qt_node_forks.append(edge_node2)
            if edge_node2.junction == switch_junct2:
                qt_node_forks.append(edge_node2)
            if len(qt_node_forks) == 2:
                break  # Found both forks
        if len(qt_node_forks) < 2:
            # Forks not found, no update
            return
        if len(qt_node_forks) > 2:
            raise IndexError(f'Found more than 2 fork nodes? {qt_node_forks}')
        self.fork_qt_notes = (qt_node_forks[0], qt_node_forks[1])

    def add_edge(self, edge):
        """
        Add an edge to this node
        :param edge: Edge to add
        """
        super().add_edge(edge)
        # Update our fork references if we're a Junction,
        self.update_fork_nodes()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        """
        Paint this QGraphicsItem
        :param painter: QPainter instance for drawing
        :param option: Styling options
        :param widget: Optionally the widget that is being painted on
        """
        # Draw circle
        painter.setPen(Qt.NoPen)
        if option.state & QStyle.State_Sunken:
            # Click and drag
            painter.setBrush(Qt.yellow)
        else:
            painter.setBrush(Qt.darkGray)
        painter.drawEllipse(self.circle_bounds)

        # Draw text
        if self.show_debug:
            font = painter.font()
            text = f'Junction({self.junction.ident})'
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QPen(Qt.black))
            text_bounds = painter.fontMetrics().boundingRect(text)
            text_bounds.moveTo(self.circle_bounds.center().toPoint())
            # text_bounds.setWidth(500)  # TODO: Sometimes fontMetrics.boundingRect returns an incorrect width?
            painter.drawText(text_bounds, text)
        else:
            text_bounds = QRectF()

        # Draw fork
        if self.fork_qt_notes is not None:
            qt_node_fork1, qt_node_fork2 = self.fork_qt_notes
            line1 = QLineF(QPointF(0, 0), self.mapFromItem(qt_node_fork1, QPointF(0, 0)))
            line2 = QLineF(QPointF(0, 0), self.mapFromItem(qt_node_fork2, QPointF(0, 0)))
            line1.setLength(self.circle_radius / 2)
            line2.setLength(self.circle_radius / 2)
            painter.setPen(QPen(Qt.red))
            painter.drawLine(line1)
            painter.drawLine(line2)
        else:
            log.error(f'No fork nodes for {self.junction.ident}')

        # calculate item bounds
        self.bounds = self.circle_bounds.united(text_bounds)


class GraphWidget(QGraphicsView):
    def __init__(self):
        """
        QGraphicsItem representing the whole graph
        """
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
        self.scale(0.8, 0.8)

        self.simulation: Optional[Simulation] = None

    def set_simulation(self, new_simulation: Simulation):
        """
        Set a new simulation to represent the graph of
        :param new_simulation: The new simulation graph
        """
        self.simulation = new_simulation

        # Clear the scene
        for item in self.scene().items():
            self.scene().removeItem(item)
        self.scene().clear()

        graph_data = nx.to_dict_of_dicts(self.simulation.graph)

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
                # Skip any edges that already connect the two nodes
                edge_already_connected = False
                for edge in edges:
                    edge_node_tup = (edge.source().junction, edge.dest().junction)
                    source_already_connected = node_start_obj in edge_node_tup
                    dest_already_connected = node_end_obj in edge_node_tup
                    if source_already_connected and dest_already_connected:
                        edge_already_connected = True
                if edge_already_connected:
                    continue

                # Convert simulation types into graphics types
                edge_obj = edge_data['object']
                if isinstance(edge_obj, Track):
                    edge = QtTrack(nodes[node_start_obj], nodes[node_end_obj], edge_obj)
                else:
                    log.warning(f'Unknown edge type: {edge_obj}')
                    edge = QtEdge(nodes[node_start_obj], nodes[node_end_obj])
                edges.append(edge)

        # Then we add all the Qt objects to the scene
        for node in nodes.values():
            self.scene().addItem(node)
        for edge in edges:
            self.scene().addItem(edge)

        self.randomize_nodes()

    def advance_simulation(self) -> Tuple[bool, int]:
        """
        Advance the simulation one time step
        :return: Tuple of (
            True if the simulation doesn't need any more updates, False otherwise,
            The current simulation time step index,
            )
        """
        if not self.simulation:
            log.warning(f'No simulation to advance: {self.simulation}')
            return False, -1
        sim_finished = not self.simulation.advance()
        # Update all the fork nodes in case any junctions switched
        for item in self.scene().items():
            if isinstance(item, QtJunction):
                item.update_fork_nodes()
        # Force repaint
        self.repaint_all(force_paint=True)
        return sim_finished, self.simulation.step

    def repaint_all(self, force_paint=False):
        """
        Repaint all the items in the scene
        :param force_paint: True if we want to repaint ourself as well, False otherwise
        """
        if force_paint:
            self.repaint()
            self.scene().update()
        for item in self.scene().items():
            item.update()
        if force_paint:
            self.repaint()
            self.scene().update()

    def randomize_nodes(self):
        """
        Randomize all the position of all the nodes in the scene
        """
        for item in self.scene().items():
            if isinstance(item, QtNode):
                item.setPos(-150 + random.randint(0, 300), -150 + random.randint(0, 300))

    def item_moved(self):
        """
        Called whenever an item in the scene is moved
        """
        if not self._timer_id:
            self._timer_id = self.startTimer(1000 / 25)

    def keyPressEvent(self, event):
        """
        Called when a key is pressed on this Widget
        :param event: The key event
        """
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
        """
        Main widget timer that calculates forces and paints items
        :param event: Timer event data
        """
        # Just repaint everything for now. Don't really want to optimize the logic
        self.repaint_all()

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
        """
        Called when the mouse scrolls on this QGraphicsView
        :param event: The mouse event data
        """
        delta = event.angleDelta().y()
        self.scale_view(math.pow(2.0, -delta / 240.0))

    def scale_view(self, scale_factor: float):
        """
        Scale the graph's view box
        :param scale_factor: Arbitrary number representing scale
        """
        factor = self.transform().scale(scale_factor, scale_factor).mapRect(QRectF(0, 0, 1, 1)).width()

        if factor < 0.07 or factor > 100:
            return

        self.scale(scale_factor, scale_factor)


class MainWidget(QWidget):
    def __init__(self):
        """
        Main widget in the window
        """
        super().__init__()

        self.graph_widget = GraphWidget()

        self.param_root = Parameter.create(name='param_root', type='group')
        self.param_one_step = parameterTypes.ActionParameter(name='One Step')
        self.param_run_cont = parameterTypes.SimpleParameter(name='Run Continuous', type='bool', default=False)
        self.param_update_delay = parameterTypes.SliderParameter(
            name='Update Delay [ms]', limits=[100, 10000], default=1000, step=50
        )
        self.param_update_delay.setValue(1000)  # TODO: Why does this not happen by default?
        self.param_sim_step_idx = parameterTypes.SimpleParameter(
            name='Simulation Step', type='int', default=0, readonly=True
        )
        self.param_show_dbg_txt = parameterTypes.SimpleParameter(name='Show debug text', type='bool', default=False)
        self.param_root.addChild(self.param_one_step)
        self.param_root.addChild(self.param_run_cont)
        self.param_root.addChild(self.param_update_delay)
        self.param_root.addChild(self.param_sim_step_idx)
        self.param_root.addChild(self.param_show_dbg_txt)
        param_tree = ParameterTree()
        param_tree.setParameters(self.param_root, showTop=False)

        self.param_root.sigTreeStateChanged.connect(self.param_change)

        self.simulation_timer = QTimer(self)
        self.simulation_timer.timeout.connect(self.step_simulation)

        self.h_layout = QHBoxLayout(self)
        self.h_layout.addWidget(param_tree, 1)
        self.h_layout.addWidget(self.graph_widget, 3)

    def param_change(self, param_root: Parameter, changes: List[Tuple[Parameter, str, Any]]):
        """
        Callback for when a parameter in the parameter tree has changed
        :param param_root: Root parameter object
        :param changes: List of parameter changes
        """
        log.debug(f'Parameter changes:{changes}')
        for param, change, data in changes:
            if param == self.param_one_step and change == 'activated':
                self.step_simulation()
            elif param == self.param_one_step and change == 'options':
                self.param_one_step.setOpts(**data)
            elif param == self.param_run_cont:
                if data is True:
                    self.simulation_timer.setInterval(self.param_update_delay.value())
                    self.simulation_timer.start()
                else:
                    self.simulation_timer.stop()
            elif param == self.param_update_delay:
                self.simulation_timer.setInterval(self.param_update_delay.value())
            elif param == self.param_sim_step_idx:
                pass  # Only updated internally
            elif param == self.param_show_dbg_txt:
                for item in self.graph_widget.scene().items():
                    if hasattr(item, 'show_debug'):
                        item.show_debug = True if data is True else False
            else:
                log.error(f'Unknown parameter change:{param}')

    def step_simulation(self):
        """
        Advance the simulation one time step
        """
        if not self.graph_widget.simulation:
            log.warning(f'No simulation to step: {self.graph_widget.simulation}')
            return
        sim_finished, sim_step_idx = self.graph_widget.advance_simulation()
        self.param_sim_step_idx.setValue(sim_step_idx)
        if sim_finished:
            self.param_one_step.setOpts(enabled=False)
            self.param_run_cont.setValue(False)
            self.param_run_cont.setOpts(enabled=False)

    def set_simulation(self, simulation: Simulation):
        """
        Set a new simulation to represent the graph of
        :param simulation: The new simulation graph
        """
        self.graph_widget.set_simulation(simulation)
        for child_param in self.param_root.children():
            child_param.setValue(child_param.defaultValue())
            child_param.setOpts(enabled=True)


class MainWindow(QMainWindow):
    def __init__(self, window_title: str):
        """
        Main Qt window
        :param window_title: Base window title
        """
        super().__init__()

        self.setMinimumSize(400, 400)
        self.bare_window_title = window_title
        self.loaded_file_path: Optional[Path] = None
        self.set_window_title()

        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu('&File')

        self.load_file_action = QAction('Load')
        self.load_file_action.triggered.connect(self.load_file)
        self.file_menu.addAction(self.load_file_action)

        self.save_file_action = QAction('Save')
        self.save_file_action.triggered.connect(self.save_file)
        self.file_menu.addAction(self.save_file_action)

        self.save_file_as_action = QAction('Save as')
        self.save_file_as_action.triggered.connect(self.save_file_as)
        self.file_menu.addAction(self.save_file_as_action)

        self.exit_action = QAction('Exit')
        self.exit_action.triggered.connect(exit_handler)
        self.file_menu.addAction(self.exit_action)

        log.debug('Creating MainWidget')
        self.main_widget = MainWidget()
        self.setCentralWidget(self.main_widget)

    def set_window_title(self):
        """
        Update the window title based on the currently loaded file
        """
        file_path_str = str(self.loaded_file_path) if self.loaded_file_path else 'No file loaded'
        self.setWindowTitle(f'{self.bare_window_title} - {file_path_str}')

    def load_file(self, file_path: Optional[Path] = None):
        """
        Load a simulation into the graph widget
        :param file_path: Path to load a file from
        """
        if file_path:
            log.debug(f'Loading provided path {file_path}')
        else:
            file_name = QFileDialog.getOpenFileName(self, 'Open Simulation File', '', 'Simulation Files (*.json)')
            if not file_name[0]:
                return  # User canceled
            file_path = Path(file_name[0])
            log.debug(f'User picked path {file_path}')

        resolved_file_path = file_path.resolve()
        new_sim = Simulation.load_from_file(resolved_file_path)
        self.loaded_file_path = resolved_file_path
        self.main_widget.set_simulation(new_sim)
        self.set_window_title()

    def save_file(self):
        """
        Save the current graph to the same file
        """
        self.save_file_as(self.loaded_file_path)

    def save_file_as(self, file_path: Optional[Path] = None):
        """
        Save the current graph to a potentially differently named file
        """
        if not self.main_widget.graph_widget.simulation:
            log.warning(f'Cannot save with no simulation loaded')
            return

        if file_path:
            log.debug(f'Saving provided path {file_path}')
        else:
            currently_loaded_name = self.loaded_file_path.name
            file_name = QFileDialog.getSaveFileName(
                self, 'Save Simulation File', currently_loaded_name, 'Simulation Files (*.json)'
            )
            if not file_name[0]:
                return  # User canceled
            file_path = Path(file_name[0])
        self.main_widget.graph_widget.simulation.save_to_file(file_path)

        self.loaded_file_path = file_path.resolve()  # Update the loaded path, incase name changed
        self.set_window_title()


def exit_handler(*args):
    """
    Basic exit handler to stop the Qt event loop
    :param args: Unused
    """
    QApplication.quit()


def excepthook(exc_type, exc_value, exc_tb):
    """
    Exception handler that provides a clean exit strategy
    :param exc_type: Exception type
    :param exc_value: Exception value
    :param exc_tb: Exception traceback
    """
    # Flush all logs
    for logger in logging.root.manager.loggerDict.values():
        for handler in logger.handlers:
            handler.flush()
    # Print the exception
    log.critical('Exception caught')
    log.critical(''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    exit_handler()


class MainApp:
    def __init__(self, window_title: str):
        """
        Main Qt application
        :param window_title: Base window title for the main window
        """
        log.debug('Creating QApplication')
        self.app = QApplication()
        self.main_window = MainWindow(window_title)

    def run(self) -> int:
        """
        Start the application and Qt event loop. Does not return unless exited.
        :return: Return code
        """
        self.main_window.show()
        # Register a custom exception handler (so that logs can be flushed)
        sys.excepthook = excepthook
        # Register exit handlers to catch ctrl+c
        signal.signal(signal.SIGINT, exit_handler)
        signal.signal(signal.SIGTERM, exit_handler)
        retcode = self.app.exec()
        return retcode

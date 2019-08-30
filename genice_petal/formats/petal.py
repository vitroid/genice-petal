# coding: utf-8
"""
Petal order parameter for analyzing ices and clathrate hydrates.

usage:
    genice II -f petal[options:separated:by:colons] > file

Petal is an order parameter reflecting the local network topology around a given node (= water molecule).
A petal graph at a node consists of rings that contain the given node.

options:
    png      Draw the hydrogen bonds with a rainbow palette according to the twist value in PNG format.
    png:CM   Draw the hydrogen bonds with color-mixing scheme in PNG format.
    png:DB   Draw the hydrogen bonds with decision-boundary coloring scheme in PNG format.
    png:SB   Draw the hydrogen bonds with simple boundary coloring scheme in PNG format.
    svg      Draw the hydrogen bonds with a rainbow palette according to the twist value in SVG format.
    svg:CM   Draw the hydrogen bonds with color-mixing scheme in SVG format.
    svg:DB   Draw the hydrogen bonds with decision-boundary coloring scheme in SVG format.
    svg:SB   Draw the hydrogen bonds with simple boundary coloring scheme in SVG format.
    yaplot   Draw the hydrogen bonds with a rainbow palette according to the twist value in YaPlot format.
    shadow   Draw shadows to the atoms (PNG and SVG)
    Ih=filename.twhist   Specify the (two-dimensional) histogram of twist parameter in pure ice Ih.
    Ic=filename.twhist   Specify the (two-dimensional) histogram of twist parameter in pure ice Ic.
    LDL=filename.twhist  Specify the (two-dimensional) histogram of twist parameter in pure LDL.
    HDL=filename.twhist  Specify the (two-dimensional) histogram of twist parameter in pure HDL.
    rotatex=30   Rotate the picture (SVG and PNG)
    rotatey=30   Rotate the picture (SVG and PNG)
    rotatez=30   Rotate the picture (SVG and PNG)
"""

# standard python modules
import sys
from collections import defaultdict
import json

# external modules
from logging import getLogger, basicConfig, INFO, DEBUG
from attrdict import AttrDict
import numpy as np
import networkx as nx

# public modules developed by myself
from countrings import countrings_nx as cr
import graphstat
from graphstat import graphstat_sqlite3


def is_spanning(ring, coord):
    logger = getLogger()
    dsum = 0
    for i in range(len(ring)):
        j,k = ring[i-1], ring[i]
        d = coord[j] - coord[k]
        d -= np.floor(d+0.5)
        dsum += d
    return np.linalg.norm(dsum) > 1e-4


def prepare(g, coord, maxring=7):
    """
    Make ring owner list
    """
    def ring_to_edge(ring):
        for i in range(len(ring)):
            yield ring[i-1], ring[i]
            
    rings = []
    subgraphs = defaultdict(nx.Graph)
    for i, ring in enumerate(cr.CountRings(g).rings_iter(maxring)):
        # make a ring list
        assert not is_spanning(ring, coord), "Some ring is spanning the cell."
        rings.append(ring)
        for node in ring:
            # make a graph made of rings owned by the node
            for edge in ring_to_edge(ring):
                subgraphs[node].add_edge(*edge)
    return rings, subgraphs

def stat(subgraphs, gc):
    """
    Make a statistics of petal types
    """
    logger = getLogger()
    ids = dict()
    for node in subgraphs:
        id =  gc.query_id(subgraphs[node])
        if id < 0:
            id = gc.register()
            logger.info("  New petal type {0}".format(id))
        ids[node] = id
    return ids

def hook2(lattice):
    global options
    lattice.logger.info("Hook2: Petal statistics.")
    database = options.database
    if database is None:
        lattice.logger.info("  Using temporary database. (volatile)")
        gc = graphstat.GraphStat()
    elif database[:4] == "http":
        lattice.logger.info("  Using MySQL: {0}".format(database))
        gc = graphstat_mysql.GraphStat(database)
    else:
        lattice.logger.info("  Using local Sqlite3: {0}".format(database))
        import os.path
        create = not os.path.isfile(database)
        if create:
            lattice.logger.info("  Create new DB.")
        gc = graphstat_sqlite3.GraphStat(database, create=create)
    
    cell = lattice.repcell 
    positions = lattice.reppositions
    graph = nx.Graph(lattice.graph) #undirected
    rings, subgraphs = prepare(graph, positions)
    ids = stat(subgraphs, gc)
    if options.json:
        # In JSON, a key must be a string.
        ids = {str(i):ids[i] for i in ids}
        print(json.dumps(ids, indent=2, sort_keys=True))
    lattice.logger.info("Hook2: end.")


    
def hook0(lattice, arg):
    global options
    logger = getLogger()
    logger.info("Hook0: ArgParser.")
    options = AttrDict()
    options.database = None
    options.json = True
    
    if arg == "":
        pass
    else:
        args = arg.split(":")
        for a in args:
            if a.find("=") >= 0:
                key, value = a.split("=")
                logger.info("Wrong option with arguments: {0} := {1}".format(key,value))
            else:
                logger.info("Flags: {0}".format(a))
                options.database = a
    logger.info("Hook0: end.")

    
hooks = {0:hook0, 2:hook2}

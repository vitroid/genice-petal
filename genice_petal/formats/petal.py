# coding: utf-8
"""
Petal order parameter for analyzing ices and clathrate hydrates.

usage:
    genice II -f petal[options:separated:by:colons] > file

Petal is an order parameter reflecting the local network topology around a given node (= water molecule).
A petal graph at a node consists of rings that contain the given node.

options:
"""

desc = { "ref": {},
         "brief": "Petal OP",
         "usage": __doc__,
         }


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
import yaplotlib as yp


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
    rings_at = defaultdict(set)
    for ring in cr.CountRings(g).rings_iter(maxring):
        # make a ring list
        assert not is_spanning(ring, coord), "Some ring is spanning the cell."
        rings.append(ring)
        ringid = len(rings) - 1
        for node in ring:
            rings_at[node].add(ringid)
        for node in ring:
            # make a graph made of rings owned by the node
            for edge in ring_to_edge(ring):
                subgraphs[node].add_edge(*edge)
    return rings, subgraphs, rings_at

def collect(subgraphs, gc):
    """
    Collect petal types
    """
    logger = getLogger()
    ids = dict()
    for node in subgraphs:
        id =  gc.query_id(subgraphs[node])
        if id < 0:
            id = gc.register()
            logger.debug("  New petal type {0}".format(id))
        ids[node] = id
    return ids


def draw_ring(nodes, positions,cell, center):
    logger = getLogger()
    v = positions[nodes]
    logger.debug(v)
    d = v - center
    d -= np.floor(d+0.5)
    return yp.Polygon((center+d*0.8) @ cell)

def hook2(lattice):
    global options
    logger = getLogger()
    logger.info("Hook2: Petal statistics.")
    database = options.database
    if database is None:
        logger.info("  Using temporary database. (volatile)")
        gc = graphstat.GraphStat()
    elif database[:4] == "http":
        logger.info("  Using MySQL: {0}".format(database))
        gc = graphstat_mysql.GraphStat(database)
    else:
        logger.info("  Using local Sqlite3: {0}".format(database))
        import os.path
        create = not os.path.isfile(database)
        if create:
            logger.info("  Create new DB.")
        gc = graphstat_sqlite3.GraphStat(database, create=create)
    
    cell = lattice.repcell.mat
    positions = lattice.reppositions
    graph = nx.Graph(lattice.graph) #undirected
    rings, subgraphs, rings_at = prepare(graph, positions)
    gids = collect(subgraphs, gc)
    if options.json:
        # In JSON, a key must be a string.
        ids = {str(i):gids[i] for i in gids}
        print(json.dumps(ids, indent=2, sort_keys=True))
    elif options.yaplot:
        # Draw top 10 most popular petal types with Yaplot.
        count = defaultdict(int)
        typical = dict()
        for node in gids:
            count[gids[node]] += 1
            typical[gids[node]] = node
        top10 = sorted(count, key=lambda gid: -count[gid])[:30]
        ranks = {gid:i for i,gid in enumerate(top10)}
        for i, gid in enumerate(ranks):
            node = typical[gid]
            logger.info("  Ranking {0}: {2} x {1} (id {3})".format(i, [len(rings[ringid]) for ringid in rings_at[node]], count[gid], gid))
        s = ""
        for node in gids:
            gid = gids[node]
            if gid in ranks:
                rank = ranks[gid]
                s += yp.Color(rank+3)
                s += yp.Layer(rank+1)
                for ringid in rings_at[node]:
                    s += draw_ring(rings[ringid], positions,cell=cell, center=positions[node])
        print(s)
    logger.info("Hook2: end.")


    
def hook0(lattice, arg):
    global options
    logger = getLogger()
    logger.info("Hook0: ArgParser.")
    options = AttrDict()
    options.database = None
    options.json = False
    options.yaplot = False
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
                if a == "yaplot":
                    options.yaplot = True
                    continue
                if a == "json":
                    options.json = True
                    continue
                options.database = a
    logger.info("Hook0: end.")

    
hooks = {0:hook0, 2:hook2}

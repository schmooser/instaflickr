# -*- coding: utf-8 -*-


def create(*args):
    return sum(map(lambda x: 0 if x == 0 else 2**max(0, x-1), args))


def add(s, bit):
    #val = 1 << (bit - 1)
    #return s if s & val == val else s + val
    return s | (1 << (bit - 1))


def sub(s, bit):
    val = 1 << (bit - 1)
    return s if s & val != val else s - val
    #return s ^ (1 << (bit - 1))


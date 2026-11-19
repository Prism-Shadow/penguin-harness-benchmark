#!/usr/bin/env python3
"""Run the real envtest API server on loopback in an offline network namespace."""
import os,sys
args=sys.argv[1:]
if not any(a=='--advertise-address' or a.startswith('--advertise-address=') for a in args):
    args.append('--advertise-address=127.0.0.1')
if not any(a=='--bind-address' or a.startswith('--bind-address=') for a in args):
    args.append('--bind-address=127.0.0.1')
real=os.path.realpath(__file__)+'.real'
os.execv(real,[real,*args])

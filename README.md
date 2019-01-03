# Python MIP (Mixed-Integer Linear Programming) Tools

Python MIP is a collection of Python tools for the modelling and solution
of Mixed-Integer Linear programs (MIPs). MIP syntax was inspired by
[Pulp](https://github.com/coin-or/pulp) and the
[Gurobi](http://www.gurobi.com) Python API. Porting Pulp and Gurobi models
should be quite easy.

Some of the main features of MIP are:

* high level modelling: write your MIP models in Python as easily as in
  high level languages such as
  [MathProg](https://en.wikibooks.org/wiki/GLPK/GMPL_(MathProg)): with
  operator overloading you can easily write linear expressions in Python;

* multi solver: works with different MIP solvers; right now Gurobi and CBC
  are supported;
  
* fast: the Python MIP package calls directly the native dynamic loadable
  library of the installed solver; models are efficiently stored and
  optimized by the solver and MIP transparently handles all communication
  ;

* cut generation: write your cut generator in python and integrate it into
  the Branch-and-Cut search;

* solution pool: query the elite set of solutions found during the search;

* mipstart: use a problem dependent heuristic to generate initial feasible
  solutions for the MIP search.


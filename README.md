# B2JS: A Brewin# to JavaScript Transpiler

This repo contains b2js, a proof-of-concept transpiler that converts a subset of Brewin# language (Project 4 in [CS 131 Fall 2024](https://ucla-cs-131.github.io/fall-24-website/)) to JavaScript in order to demonstrate the implementation of lazy evaluation.

The transpiler is intentionally created to be minimal rather than feature-rich or 100% compliance. It implements the following features:
* Most of the Project 2 (Brewin) language features
* Need semantics and lazy evaluation
* Short-circuiting boolean expressions

It does not support the following:
* Error handling (b2js assumes the program to be valid, i.e., free of syntax and semantic errors)
* Function overloading
* Exceptions
* Input functions (`inputi` and `inputs`)

Moreover, b2js simply maps the `print` built-in function to `console.log` in JS. The latter adds a space between parameters while the former doesn't.

While the project is created to simply demonstrate lazy evaluation with the usage of closure, the missing features or incompliance is not deemed a big deal. I don't have a plan to properly implement them at the moment.

## Usage
The command line options of b2js is as follows:
```
python b2js.py [-s STEP] [-o OUTPUT] input.br
```

The `-s` option (0-3) selects one of the transpilation variants (see the b2js and generated code for details):

* Step 0: Baseline, no lazy evaluation
* Step 1: Basic lazy evaluation with closures, no caching support
* Step 2: Lazy evaluation and caching enabled, but with incorrect capture semantics
* Step 3 (default): Brewin#-compatible lazy evaluation semantics with snapshot

The transpiling output will be written to the specified file when the `-o` option is present, otherwise it will be printed to standard output.

## Licensing and Attribution
This project is created by Boyan Ding and contains supporting components from UCLA CS 131 Fall 2024 project repo. This code is distributed under the [MIT License](https://github.com/dboyan/b2js/COPYING).

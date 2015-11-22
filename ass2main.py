import os
import sys

arguments = []
for argument in sys.argv:
	arguments.append(argument)

protocol = arguments[1]
input_file = arguments[2]
no_processors = int(arguments[3])
cache_size = int(arguments[4])
associativity = int(arguments[5])
block_size = int(arguments[6])


if protocol.lower() == "mesi":
	os.system("pypy MESI.py" + " " + str(protocol) + " "  + str(input_file) + " "  + str(no_processors) + " "  + str(cache_size) + " "  + str(associativity) + " "  + str(block_size))
elif protocol.lower() == "dragon":
	os.system("pypy DRAGON.py" + " " + str(protocol) + " "  + str(input_file) + " "  + str(no_processors) + " "  + str(cache_size) + " "  + str(associativity) + " "  + str(block_size))

import sys

class Processor(object):

	def __init__(self):
		self.hello = "Heloo worrlddd"
		print self.hello

	def getType(self):
		return "Dragon"

i=0
arguments = []
for argument in sys.argv:
	arguments.append(argument)
	i +=1

protocol = arguments[1]
input_file = arguments[2]
no_processors = arguments[3]
cache_size = arguments[4]
associativity = arguments[5]
block_size = arguments[6]
import sys

class MemAccess(object):
	accTypes = {
			0: "fetch_instr",
			2: "read",
			3: "write"}
	def __init__(self, accType, address):
		self.type = accTypes.get(accTypes)
		self.memLoc = address

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

inputfile = open("weather", "r")

MemAccessList = []

for line in inputfile:
	MemAccessList.append(MemAccess(str.split(line)))
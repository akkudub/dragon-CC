import sys
import csv
import pylru
import math

arguments = []
for argument in sys.argv:
	arguments.append(argument)

protocol = arguments[1]
input_file = arguments[2]
no_processors = int(arguments[3])
cache_size = int(arguments[4])
associativity = int(arguments[5])
block_size = int(arguments[6])

word_size = 2
words_per_block = int(block_size/word_size)
fileList = []

cacheSets = int(math.ceil(cache_size/(associativity * block_size)))
CPU = []
writeBlock = []

#bus signals
# "BusRdNotShared"
# "BusRdShared"
# "BusUpdNotShared"
# "BusUpdShared"

currBusSignal = ""
currBusData = 0
totalBusTraffic = 0
busMutex = -1

class Processor(object):

	def __init__(self, no, trace, cache):
		self.no = no
		self.trace = trace
		self.cache = cache
		self.stalls = 0
		self.cycles = 0
		self.misses = 0
		self.instr_count = 0
		self.stalled_instr = [0, 0, None]
		self.done = False
		self.memacc = 0

	def getState(self, address):
		block = int(math.floor(address/block_size))
		blockSet = block % cacheSets
		if block in self.cache[blockSet]:
			return self.cache[blockSet].peek(block)
		else:
			return "I"

	def setState(self, address, state):
		block = int(math.floor(address/block_size))
		blockSet = block % cacheSets
		if state == "I":
			if block in self.cache[blockSet]:
				del self.cache[blockSet][block]			
		else:
			self.cache[blockSet][block] = state

	def setState_bypassLRU(self, address, state):
		block = int(math.floor(address/block_size))
		blockSet = block % cacheSets
		if state == "I":
			if block in self.cache[blockSet]:
				del self.cache[blockSet][block]			
		else:
			self.cache[blockSet].set_bypass_lru(block, state)

	def __str__(self):
		return "Processor no: " + str(self.no)
		
	def __repr__(self):
		return "Processor no: " + str(self.no) 

def make_eviction_handler(processor, set):
    def eviction(blockNum, state):
        global totalBusTraffic
        if state == "M":
            totalBusTraffic += block_size            
            for core in CPU:
            	if core.no == processor:
		            core.stalls += 100
		            core.stalled_instr = [4, blockNum * block_size, None]
		elif state == "Sm":
			for core in CPU:
				if core.no != processor:
					if core.getState(blockNum * block_size) == "Sc":
						core.setState_bypassLRU(blockNum * block_size, "Sm")
						return



    return eviction

def appendToWriteBlock(core):
	if core not in writeBlock:
		writeBlock.append(core)

try:
	#initialising
	for i in range(0, no_processors):
		filename = input_file + "/" + input_file + str(i+1) + ".PRG"
		tempFile = open(filename, "rb")

		fileList.append(tempFile) #to close later

		traceFileReader = csv.reader(tempFile, delimiter=' ')
		cache = []
		for j in range(0, cacheSets):
			cache.append(pylru.lrucache(associativity, make_eviction_handler(i, j)))

		CPU.append(Processor(i, traceFileReader, cache))

	all_done = False

	#starting processing
	while not all_done:
		for core in CPU:
			
			#if core is functioning normally

			if core.stalls <= 0:
				if core not in writeBlock:
					try:
						nextMemAccess = core.trace.next()
					except StopIteration:
						#no more left! yay!
						core.done = True
						# print "core " + str(core.no) + "ended, and "
						all_done = True
						for doneCore in CPU:
							# print "core " + str(doneCore.no) + "is " + str(doneCore.done)
							if doneCore.done == False:
								all_done = False
						continue
					#more left, comtinue
					if core.instr_count % 100000 == 0:
						print('cpu ' + str(core.no) + ' has read ' + str(core.instr_count) + ' instructions')
					nextInstr = int(nextMemAccess[0])
					nextAddr = int(nextMemAccess[1], 16)
					core.instr_count += 1
					core.cycles += 1
					#fetch instruction
					if nextInstr == 0:
						pass

					#read
					elif nextInstr == 2:
						state = core.getState(nextAddr)
						if state == "M":
							core.setState(nextAddr, "M")
						elif state == "E":
							core.setState(nextAddr, "E")
						elif state == "Sc":
							core.setState(nextAddr, "Sc")
						elif state == "Sm":
							core.setState(nextAddr, "Sm")
						#PrRdMiss
						elif state == "I":
							core.misses += 1
							totalBusTraffic += block_size
							#check if shared, basically BusRd
							shared = False
							SMFound = False
							lastSc = None
							lastSm = None
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if sharedState != "I":
									shared = True
									if sharedState == "M":
										coreShared.setState_bypassLRU(nextAddr, "Sm")
									if sharedState == "E":
										coreShared.setState_bypassLRU(nextAddr, "Sc")
									if sharedState == "Sm":
										lastSm = coreShared;
										SMFound = True
									if sharedState == "Sc":
										lastSc = coreShared

							if not shared:
								core.stalls += 100
								core.setState(nextAddr, "E")
								core.stalled_instr = [nextInstr, nextAddr, None]
							else:
								if SMFound != None:
									appendToWriteBlock(lastSm)
									core.stalled_instr = [nextInstr, nextAddr, lastSm]
								else:
									appendToWriteBlock(lastSc)
									core.stalled_instr = [nextInstr, nextAddr, lastSc]
								core.stalls += words_per_block
								core.setState(nextAddr, "Sc")								

					#write
					elif nextInstr == 3:
						state = core.getState(nextAddr)
						shared = False
						if state == "M":
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if coreShared != core:
									if sharedState != "I":
										#stall the other cores that should get the data
										shared = True
										coreShared.stalls += 1
										coreShared.stalled_instr = [5, nextAddr, core]
										totalBusTraffic += 2
										coreShared.setState(nextAddr, "Sc")

							if shared:							
								core.setState(nextAddr, "Sm")
								appendToWriteBlock(core)
							else:
								core.setState(nextAddr, "M")
							
						elif state == "E":
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if coreShared != core:
									if sharedState != "I": #should not happen
										#stall the other cores that should get the data
										shared = True
										coreShared.stalls += 1
										coreShared.stalled_instr = [5, nextAddr, core]
										totalBusTraffic += 2
										coreShared.setState(nextAddr, "Sc")

							if shared:#should not happen
								core.setState(nextAddr, "Sm")
								appendToWriteBlock(core)
							else:
								core.setState(nextAddr, "M")

						elif state == "Sc":
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if coreShared != core:
									if sharedState != "I": #should not happen
										#stall the other cores that should get the data
										shared = True
										coreShared.stalls += 1
										coreShared.stalled_instr = [5, nextAddr, core]
										totalBusTraffic += 2
										coreShared.setState_bypassLRU(nextAddr, "Sc")

							if shared:#should not happen
								core.setState(nextAddr, "Sm")
								appendToWriteBlock(core)
							else:
								core.setState(nextAddr, "M")

						elif state == "Sm":
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if coreShared != core:
									if sharedState != "I": #should not happen
										#stall the other cores that should get the data
										shared = True
										coreShared.stalls += 1
										coreShared.stalled_instr = [5, nextAddr, core]
										totalBusTraffic += 2
										coreShared.setState_bypassLRU(nextAddr, "Sc")

							if shared:#should not happen
								core.setState(nextAddr, "Sm")
								appendToWriteBlock(core)
							else:
								core.setState(nextAddr, "M")

						#PrWrMiss
						elif state == "I":
							core.misses += 1
							totalBusTraffic += block_size
							#check if shared
							shared = False
							SMFound = False
							lastSc = None
							lastSm = None
							for coreShared in CPU:
								sharedState = coreShared.getState(nextAddr)
								if sharedState != "I":
									shared = True
									#to uppdate the rest
									coreShared.stalls += 1
									coreShared.stalled_instr = [5, nextAddr, core]
									totalBusTraffic += 2
									if sharedState == "M":
										coreShared.setState_bypassLRU(nextAddr, "Sm")
									if sharedState == "E":
										coreShared.setState_bypassLRU(nextAddr, "Sc")
									if sharedState == "Sm":
										lastSm = coreShared;
									if sharedState == "Sc":
										lastSc = coreShared

							if not shared:
								core.stalls += 100
								core.setState(nextAddr, "E")
								core.stalled_instr = [nextInstr, nextAddr, None]
							else:
								if SMFound != None:
									appendToWriteBlock(lastSm)
									core.stalled_instr = [nextInstr, nextAddr, lastSm]
								else:
									appendToWriteBlock(lastSc)
									core.stalled_instr = [nextInstr, nextAddr, lastSc]
								core.stalls += words_per_block
								core.setState(nextAddr, "Sm")
				else:
					core.cycles += 1
					noStall = True
					for tempcore in CPU:
						if tempcore.stalls > 0:
							noStall = False
					if noStall:
						writeBlock = []
					# if core != None:
						# print "Core " + str(core.no) + " blocked"
			#if core has a stall
			else:
				#try to acquire bus 
				core.cycles += 1
				# if core.cycles % 100000 == 0:
				# 	print "writeBlock " + str(writeBlock)
				if busMutex == -1 or busMutex == core.no:
					#bus acquired
					busMutex = core.no
					core.stalls -= 1
					# if core.instr_count % 100000 == 0:
					# 	print "Core " + str(core.no) + " stalled with " + str(core.stalls)
					if core.stalls == 0:
						#do everything and release bus
						busMutex = -1
						stalledInstr = core.stalled_instr[0]
						stalledAddr = core.stalled_instr[1]
						blockedCore = core.stalled_instr[2]
						#fetch instr
						# for tempcore in CPU:	
						# 	print "Core " + str(tempcore.no) + " stalled with " + str(tempcore.stalled_instr) + "state " + tempcore.getState(stalledAddr)
						if stalledInstr == 0:
							pass
						#read
						elif stalledInstr == 2:
							#assign yourself as the Sm in case there are any reads
							isShared = False
							SMFound = False
							for coreShared in CPU:
								sharedState = coreShared.getState(stalledAddr)
								if sharedState != "I":
									isShared = True
									#change others to shared
									if sharedState == "M" or sharedState == "E":
										coreShared.setState_bypassLRU(nextAddr, "Sc")
									if sharedState == "Sm":
										SMFound = True

							if isShared:
								if SMFound:
									core.setState(stalledAddr, "Sc")
								else:
									core.setState(stalledAddr, "Sm")
							else:
								core.setState(stalledAddr, "E")
						#write
						elif stalledInstr == 3:
							#assign yourself as the Sm or M at all times
							isShared = False
							for coreShared in CPU:
								sharedState = coreShared.getState(stalledAddr)
								if sharedState != "I":
									isShared = True
									#change others to shared
									coreShared.setState_bypassLRU(nextAddr, "Sc")

							if isShared:
								core.setState(stalledAddr, "Sm")
							else:
								core.setState(stalledAddr, "M")
						#eviction is happening
						elif stalledInstr == 4:
							core.setState(stalledAddr, "I")

						#BusUpdate Stall
						elif stalledInstr == 5:
							core.setState(stalledAddr, "Sc")

						#removed blocked core from the list
						if blockedCore in writeBlock:
							writeBlock.remove(blockedCore)
							# print "removed core no " + str(blockedCore.no)
		
finally:
	#printing statistics
	print("Done!")
	print("\n")
	for core in CPU:
		print("CPU " + str(core.no) + " misses: " + str(core.misses))
	print("Traffic: " + str(totalBusTraffic) + " bytes")
	for core in CPU:
		print("CPU " + str(core.no) + " cycles: " + str(core.cycles))

	for f in fileList:
		f.close

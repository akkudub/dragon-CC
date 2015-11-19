import csv
import pylru
import argparse
import math

word_size = 2

# Arguments
parser = argparse.ArgumentParser(description='Cache Simulator')
parser.add_argument('protocol', type=str)
parser.add_argument('input_file', type=str)
parser.add_argument('processor_count', type=int, default=4, nargs='?')
parser.add_argument('cache_size', type=int, default=4096, nargs='?')
parser.add_argument('associativity', type=int, default=1, nargs='?')
parser.add_argument('block_size', type=int, default=16, nargs='?')
args = parser.parse_args()

# Stats
cycles = []
misses = []
instruction_count = []
bus_traffic = 0

sets_count = int(math.ceil(args.cache_size / (args.associativity * args.block_size)))
stalls = []
stalled_instruction = []
caches = []
fs = []
readers = []
done = []
bus_mutex = -1

def is_everyone_stalled():
    for i in range(0, args.processor_count):
        if stalls[i] == 0:
            return False
    return True

def get_state(cpu, address):
    block_num = int(math.floor(address / args.block_size))
    set_num = block_num % sets_count
    if not (block_num in caches[cpu][set_num]):
        return "I"
    else:
        return caches[cpu][set_num][block_num]
    
def set_state(cpu, address, state):
    block_num = int(math.floor(address / args.block_size))
    set_num = block_num % sets_count
    
    if state == "I" and get_state(cpu, address) != "I":
        del caches[cpu][set_num][block_num]
    else:
        caches[cpu][set_num][block_num] = state

def shared_signal(address):
    for i in range(0, args.processor_count):
        if get_state(i, address) != "I":
            return True
    return False

def make_eviction_handler(cpu, set):
    def eviction(key, value):
        pass
        #print(str(key) + " evicted from cpu " + str(cpu) + " cache!")
    return eviction

try:
    print("Initialising...")
    for i in range(0, args.processor_count):
        filename = args.input_file + str(i+1) + '.PRG'
        fs.append(open(filename, 'rb'))
        stalls.append(0)
        cycles.append(0)
        misses.append(0)
        instruction_count.append(0)
        
        stalled_instruction.append(False)
        done.append(False)
        
        cache = []
        for j in range(0, sets_count):
            #cache.append(pylru.lrucache(args.associativity, make_eviction_handler(i, j)))
            cache.append(pylru.lrucache(args.associativity))
        caches.append(cache)
    for f in fs:
        readers.append(csv.reader(f, delimiter=' '))
    print("Done!")
    
    print("Running simulation...")
    all_done = False
    while not all_done:
        for i in range(0, args.processor_count):
            cycles[i] += 1
            
            if stalls[i] > 0:
                #try acquire the shared bus
                if bus_mutex == i or bus_mutex == -1:
                    #acquire the bus
                    bus_mutex = i
                    
                    if is_everyone_stalled():
                        #print("everyone is stalled")
                        cycles[i] += stalls[i] - 1
                        for j in range(0, args.processor_count):
                            if i == j:
                                continue
                            cycles[j] += stalls[i]
                        stalls[i] = 0
                    else:
                        stalls[i] -= 1
                    
                    if stalls[i] == 0:
                        bus_mutex = -1
                        instruction, address = stalled_instruction[i]
                        if instruction == 0:
                            pass
                        elif instruction == 2:
                            if shared_signal(address):
                                set_state(i, address, 'S')
                            else:
                                set_state(i, address, 'E')
                        elif instruction == 3:
                            set_state(i, address, 'M')
                        elif instruction == 4:
                            set_state(i, address, 'I')
                continue
            
            row = None
            try:
                row = readers[i].next()
            except StopIteration:
                if not done[i]:
                    done[i] = True
                    print('cpu ' + str(i) + ' reached end! Rest:' + str(done))
                all_done = True
                for j in range(0, args.processor_count):
                    if done[j] == False:
                        all_done = False
                continue
            
            # 0 = fetch
            # 2 = read
            # 3 = write
            instruction = int(row[0])
            address = int(row[1], 16)
            
            if instruction_count[i] % 100000 == 0:
                print('cpu ' + str(i) + ' has read ' + str(instruction_count[i]) + ' instructions')
            #print('cpu ' + str(i) + ': ' + str(instruction) + ' ' + str(address))
            
            instruction_count[i] += 1
            
            if instruction == 0:
                pass
            elif instruction == 2:
                state = get_state(i, address)
                
                if state == "M":
                    pass
                elif state == "E":
                    pass
                elif state == "S":
                    pass
                elif state == "I":
                    misses[i] += 1
                    stalls[i] += 100
                    bus_traffic += word_size
                    stalled_instruction[i] = (instruction, address)
            elif instruction == 3:
                state = get_state(i, address)
                
                if state == "M":
                    pass
                elif state == "E":
                    set_state(i, address, 'M')
                elif state == "S":
                    flusher = -1
                    for j in range(0, args.processor_count):
                        other_state = get_state(j, address)
                        if other_state == "S":
                            if flusher == -1:
                                flusher = j
                                stalls[j] += 100
                                stalled_instruction[j] = (4, address)
                            else:
                                set_state(j, address, 'I')
                    set_state(i, address, 'M')
                elif state == "I":
                    if shared_signal(address):
                        flusher = -1
                        for j in range(0, args.processor_count):
                            other_state = get_state(j, address)
                            if other_state != "I":
                                if flusher == -1:
                                    flusher = j
                                    stalls[j] += 100
                                    stalled_instruction[j] = (4, address)
                                else:
                                    set_state(j, address, 'I')
                    misses[i] += 1
                    stalls[i] += 100
                    bus_traffic += word_size
                    stalled_instruction[i] = (instruction, address)
finally:
    print("Done!")
    print("")
    for i in range(0, args.processor_count):
        print("CPU " + str(i) + " misses: " + str(misses[i]))
    print("Traffic: " + str(bus_traffic) + " bytes")
    for i in range(0, args.processor_count):
        print("CPU " + str(i) + " cycles: " + str(cycles[i]))
    
    for f in fs:
        f.close()

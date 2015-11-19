import csv
import pylru
import argparse
import math

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
stalled_instructions = []
caches = []
fs = []
readers = []
done = []
bus_mutex = -1
word_size = 2

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
    
    if state == "I":
        if get_state(cpu, address) != "I":
            del caches[cpu][set_num][block_num]
    else:
        caches[cpu][set_num][block_num] = state

def is_all_stalled():
    for i in range(0, args.processor_count):
        if len(stalled_instructions[i]) == 0:
            return False
    return True

def get_flusher(address):
    for i in range(0, args.processor_count):
        for j in range(0, len(stalled_instructions[i])):
            if stalled_instructions[i][j]['instruction'] == 4 and stalled_instructions[i][j]['address'] == address:
                return i
    return -1

def shared_signal(address):
    for i in range(0, args.processor_count):
        if get_state(i, address) != "I":
            return True
    return False
    
def make_eviction_handler(cpu, set):
    def eviction(block_num, state):
        #print(str(block_num) + " evicted from cpu " + str(cpu) + " cache !")
        if state == "M":
            bus_traffic += args.block_size
            stalled_instructions[cpu].append({
                'stalls': 100,
                'instruction': 4,
                'address': block_num * args.block_size
            })
    return eviction

try:
    print("Initialising...")
    for i in range(0, args.processor_count):
        filename = args.input_file + str(i+1) + '.PRG'
        fs.append(open(filename, 'rb'))
        
        cycles.append(0)
        misses.append(0)
        instruction_count.append(0)
        stalled_instructions.append([])
        done.append(False)
        
        cache = []
        for j in range(0, sets_count):
            cache.append(pylru.lrucache(args.associativity, make_eviction_handler(i, j)))
        caches.append(cache)
    for f in fs:
        readers.append(csv.reader(f, delimiter=' '))
    print("Done!")
    
    print("Running simulation...")
    all_done = False
    while not all_done:
        for i in range(0, args.processor_count):
            if len(stalled_instructions[i]) > 0:
                cycles[i] += 1
                
                #try acquire the shared bus
                if bus_mutex == i or bus_mutex == -1:
                    #acquire the bus
                    bus_mutex = i
                    
                    if is_all_stalled():
                        #print("everyone is stalled")
                        cycles[i] += stalled_instructions[i][0]['stalls'] - 1
                        for j in range(0, args.processor_count):
                            if i == j:
                                continue
                            cycles[j] += stalled_instructions[i][0]['stalls']
                        stalled_instructions[i][0]['stalls'] = 0
                    else:
                        stalled_instructions[i][0]['stalls'] -= 1
                    
                    if stalled_instructions[i][0]['stalls'] == 0:
                        bus_mutex = -1
                        instruction = stalled_instructions[i][0]['instruction']
                        address = stalled_instructions[i][0]['address']
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
                        stalled_instructions[i].pop(0)
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
                
            cycles[i] += 1
            
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
                    set_state(i, address, 'M')
                elif state == "E":
                    set_state(i, address, 'E')
                elif state == "S":
                    set_state(i, address, 'S')
                elif state == "I":
                    misses[i] += 1
                    bus_traffic += args.block_size
                    stalled_instructions[i].append({
                        'stalls': 100,
                        'instruction': instruction,
                        'address': address
                    })
            elif instruction == 3:
                state = get_state(i, address)
                
                if state == "M":
                    pass
                elif state == "E":
                    set_state(i, address, 'M')
                elif state == "S":
                    flusher = get_flusher(address)
                    for j in range(0, args.processor_count):
                        other_state = get_state(j, address)
                        if other_state == "S":
                            if flusher == -1:
                                flusher = j
                                bus_traffic += args.block_size
                                stalled_instructions[j].append({
                                    'stalls': 100,
                                    'instruction': 4,
                                    'address': address
                                })
                            else:
                                set_state(j, address, 'I')
                    set_state(i, address, 'M')
                elif state == "I":
                    if shared_signal(address):
                        flusher = get_flusher(address)
                        for j in range(0, args.processor_count):
                            other_state = get_state(j, address)
                            if other_state != "I":
                                if flusher == -1:
                                    flusher = j
                                    bus_traffic += args.block_size
                                    stalled_instructions[j].append({
                                        'stalls': 100,
                                        'instruction': 4,
                                        'address': address
                                    })
                                else:
                                    set_state(j, address, 'I')
                    misses[i] += 1
                    bus_traffic += args.block_size
                    stalled_instructions[i].append({
                        'stalls': 100,
                        'instruction': instruction,
                        'address': address
                    })
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

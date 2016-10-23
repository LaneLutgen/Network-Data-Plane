'''
Created on Oct 12, 2016

@author: mwitt_000
'''
import queue
import threading


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.queue = queue.Queue(maxsize);
    
    ##get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)
        
## Implements a network layer packet (different from the RDT packet 
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths 
    dst_addr_S_length = 5
    
    #allocate 1 byte for the fragment flag
    frag_flag_length = 1
    
    #allocate 2 bytes for the offset (which is multiplied by 8)
    offset_length = 2
    
    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    def __init__(self, dst_addr, data_S, frag_flag, offset):
        self.dst_addr = dst_addr
        self.data_S = data_S
        self.frag_flag = frag_flag
        self.offset = offset
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
    
    ## Used to set the packet as being fragmented
    def set_fragment(self, frag_flag, offset):
        self.frag_flag = frag_flag
        self.offset = offset
            
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        byte_S += str(self.frag_flag)
        byte_S += str(self.offset).zfill(self.offset_length)
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst_addr = int(byte_S[0 : NetworkPacket.dst_addr_S_length])
        frag_flag = int(byte_S[NetworkPacket.dst_addr_S_length : NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length])
        offset = int(byte_S[NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length : NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length + NetworkPacket.offset_length])
        data_S = byte_S[NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length + NetworkPacket.offset_length : ]
        return self(dst_addr, data_S, frag_flag, offset)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False
        self.fragmented = False #for thread termination
        self.pkt_data = ''
    
    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)
       
    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        mtu_L = 80
        while len(data_S) + NetworkPacket.dst_addr_S_length > NetworkPacket.dst_addr_S_length:
            p = NetworkPacket(dst_addr, data_S[:mtu_L - NetworkPacket.dst_addr_S_length], 0 , 0)
            self.out_intf_L[0].put(p.to_byte_S()) #send packets always enqueued successfully
            print('%s: sending packet "%s"' % (self, p))
            data_S = data_S[mtu_L - NetworkPacket.dst_addr_S_length:]
        
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        if pkt_S is not None:
            p = NetworkPacket.from_byte_S(pkt_S)
            if self.fragmented == False and p.frag_flag == 1:
                print('%s: packet fragmented, awaiting next fragment...' % self)
                self.prior_packet = p
                self.fragmented = True
                self.pkt_dst_addr = p.dst_addr
                self.pkt_data = p.data_S
            elif self.fragmented == True and p.frag_flag == 1:
                print('%s: packet fragmented, awaiting next fragment...' % self)
                #Concatenate packets
                self.pkt_data += p.data_S

            elif self.fragmented == True and p.frag_flag == 0:
                print('%s: final fragment received, reassembling message...' % self)
                #Final packet fragment
                self.pkt_data += p.data_S
                final = NetworkPacket(self.pkt_dst_addr, self.pkt_data, 0, 0)
                print('%s: received message "%s"' % (self, final))
                pass
            else:
                #No packets were fragmented
                print('%s: received message "%s"' % (self, pkt_S))
                
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router described in class
class Router:
    
    ##@param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces 
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces
    def forward(self):
        mtu_L = 30;
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                #get packet from interface i
                pkt_S = self.in_intf_L[i].get()
                #if packet exists make a forwarding decision
                if pkt_S is not None:
                    p = NetworkPacket.from_byte_S(pkt_S)
                    data_S = p.data_S
                    if len(p.to_byte_S()) > mtu_L:
                        #fragment the packets
                        offset = 0
                        len_data = len(data_S)
                        len_pkt = len(pkt_S)
                        while (len(data_S) + NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length + NetworkPacket.offset_length) > NetworkPacket.dst_addr_S_length + NetworkPacket.frag_flag_length + NetworkPacket.offset_length:
                            new_packet = NetworkPacket(p.dst_addr, data_S[:mtu_L - NetworkPacket.dst_addr_S_length - NetworkPacket.frag_flag_length - NetworkPacket.offset_length], 1 , offset)
                            data_S = data_S[mtu_L - NetworkPacket.dst_addr_S_length - NetworkPacket.frag_flag_length - NetworkPacket.offset_length:]
                            offset = len_data - len(data_S)
                            #Check if this is the last fragmented packet, if so set the flag to 0 to indicate final packet
                            if len(data_S) == 0:
                                new_packet.frag_flag = 0
                            
                            self.out_intf_L[i].put(new_packet.to_byte_S())
                            print('%s: forwarding packet "%s" from interface %d to %d' % (self, new_packet, i, i))
                    else:
                        self.out_intf_L[i].put(p.to_byte_S(), True)
                        print('%s: forwarding packet "%s" from interface %d to %d' % (self, p, i, i))
                        
                    # HERE you will need to implement a lookup into the 
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i
                    
                   
            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
                pass
                
    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return
           
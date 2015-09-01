
# coding: utf-8

# In[ ]:

import socket
import threading
import sys
import time

import RPi.GPIO as GPIO

#166.170.45.169
#10.0.0.12
#98.202.207.237


# In[ ]:

class MessageStruct():
    def __init__(self, text, sender, destination): # intrep = intended recipient
        self.packet= {'head':'msg','rdtext': (text)}
        self.destination = destination
        self.finalbytes = bytes(str(self.packet),"UTF-8")
        self.finalPacket = (destination, self.finalbytes)


# In[ ]:

class LinkStruct():
    def __init__(self, url, sender, destination): # intrep = intended recipient
        self.packet= {'head':'link','url':url}
        self.destination = destination
        self.finalbytes = bytes(str(self.packet),"UTF-8")


# #Pulse and Destination Structures
#  Destination of
#      'A' means send to all
#  
#  Pulse of
#      '*' means open and linked
#      '!' message is queued to be recieved by you
#      '?' I am ready to recieve your message

# In[18]:

class Peer():
    def __init__(self, conf = './ServerDefault.conf',):
        try:
            config = open(conf,'r')
        except FileNotFoundError:
            self.genConfig(conf)
            config = open(conf,'r')
        exec(config.read())
        config.close()
        self.accept = threading.Thread(target=self.acceptPeers,kwargs={'MaxConnections':7})
        self.seek = threading.Thread(target=self.seekPeers,kwargs={'MaxConnections' :7 })
        #self.pdbg = threading.Thread(target=self.heartbeat,kwargs={'interval':3})
        self.conManage = threading.Thread(target=self.monitorConnections)
        self.stateMachine = threading.Thread(target=self.StMach)
        self.packetStack = [MessageStruct("Everything is up and running!","Server:","*").finalPacket,]
        self.messageHistory = []
        self.missLimit = 100
        self.state = 'High'
        self.changed = False
        self.Peers = []
        self.badPeers = []
        self.stateOfPeers = []
        self.timeAlive = 0
    
    def start(self):
        self.live = True;
        self.accept.start()
        self.seek.start()
        self.conManage.start()
        #self.pdbg.start()
        self.stateMachine.start()
        
    
    def stop(self):
        self.live = False
        print("Allowing Timeout")
        sys.stdout.flush()
        #self.pdbg.join()
        self.seek.join()
        self.send.join()
        print("Stopped")
    
    def StMach(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.sensorPin, GPIO.IN, GPIO.PUD_DOWN)
    
        count = 0
        prevState = False
        currState = False
        
        while self.live:
            time.sleep(.1)
            prevState = currState
            currState = GPIO.input(self.sensorPin)
            count = count + 1
            time.sleep(2)
            if prevState != currState:
                self.state = "High" if currState else "Low"
                self.changed = True
                self.timeAlive = count
                print("I changed my state: %s" % self.state)
               

    def seekPeers(self, MaxConnections = 7):
        while self.live:
            #print("Servers Active: %s" % self.Peers)
            #peersOnNetwork = self.FindLife()
            #for i in peersOnNetwork:  #expect peersOnNetwork to be a list with structure {host, port}
            for i in range (1 , 35):
                ip = self.baseIP + str(i)
                #con = self.connect(i[0])
                for k in self.Peers:
                    if (k[1][0] == ip):  
                        break                    
                else: #Should Only execute when above for loop exits normally IE. we aren't already connected
                    #print("Trying: %s:" % ip)
                    try:
                        if ip == self.myIP: break
                        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                        s.settimeout(.5)
                        #print("-------------------------------------------Trying to seek: %s" % ip)
                        s.connect((ip, self.port))
                        s.settimeout(None)
                        newPeer = (s, (ip, self.port))
                        self.Peers.append(newPeer)
                        print("New Connection Sought: %s" % (self.Peers[-1][1][0],))
                    except:
                        None

    def acceptPeers(self,MaxConnections = 7):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host,self.port))
        self.sock.settimeout(3)
        self.sock.listen(MaxConnections)
        while self.live and (len(self.Peers) < MaxConnections):
            try:
                self.Peers.append(self.sock.accept())
            except:
                continue
            print("New Connection Accepted:",self.Peers[-1][1][0])
            sys.stdout.flush()
        self.sock.close()                          
       
    
     
    def monitorConnections(self):
        while self.live:
            self.statePacketManager()
            self.digestMulticast()
            self.distributePackets()
            self.prunePeers()
            
    def prunePeers(self):
        #badPeers is a list of peers that have missed connections, and how many times that peer has missed its connection
        #self.missLimit is how many times a Peer can miss a transmission before getting kicked
        for k in self.badPeers:
            #print(k)
            if k[1] > self.missLimit:
                for j in range( len(self.Peers)):
                    if self.Peers[j][0] == k[0]:
                        print("Peer " + self.Peers[j][1][0] + " unresponsive. Kicking...")
                        self.Peers.pop(j)
                        self.badPeers.remove(k)
                        break
                
            
                    
    def statePacketManager(self):
    #This looks at the current sensor state and adds its value to the packetStack. Its done here in the MonitorConnections()
    #thread in to be sure that packetStack isn't modified by an outside thread during self.distributePackets()
        if self.changed: 
            #each update sent like the following: ( myIP, (state, timeAlive) )
            #So each peer can evaluate what the other sends, and recieve a data structure with its time, IP and its state. Easy to use
            msgContents =  "(" + self.myIP + " : (" + self.state + ', ' + str( self.timeAlive ) + " ) )" 
            self.packetStack.append( MessageStruct( msgContents ,self.myIP, '*' ).finalPacket)
            print("added Multicast")
            #for i in self.Peers:
            #    print("Queueing Packet for " + i[1][0])
            #    self.packetStack.append( MessageStruct( msgContents ,self.myIP, i[1][0] ).finalPacket)
            self.changed = False
            
            
            
   

    def digestMulticast(self):
        
    
        #Get's rid "Send to all" packets to remove weird packet Popping errors
        managedStack = []
        #print("Added HeartBeat")
        for i in range(len(self.packetStack) ):
            if self.packetStack[i][0] == '*':
                for k in self.Peers:
                    tempPack = MessageStruct( self.evalPacket(self.packetStack[i][1] ), self.myIP, k[1][0])
                    print("Queueing Packet for " + i[1][0])
                    managedStack.append( tempPack.finalPacket )
            else:
                managedStack.append( self.packetStack[i])
        self.packetStack = managedStack
        #print("PacketStack: %s" % self.packetStack)
        #print("PacketStack Length: %s" % len(self.packetStack))
        None
        
        
    def distributePackets(self):
        #Manages when and where to call sendPacket() to. If no packet is ready, sends in an empty one it it listens
        if len(self.Peers) != 0:
            for k in self.Peers:
                if ( len(self.packetStack) != 0) and (self.packetStack[0][0] == k[1][0] ):
                    self.sendPacket(self.packetStack[0])
                else:
                    self.sendPacket( (k[1][0], '' ))
                    
     

    def sendPacket(self, packetTuple): 
        #given a tuple (ip Destination, finalBytes to send) this method first tries to find the Peer that holds
        #that IP. First listens on that connection for a time, then sends its own. No handshakes involved. It
        #only pops from the packetStack if the message is successfully sent (conn.send() doesn't time out)
        #Uses first instance of IP adddr found. Meaning a device connected multiple times is invisible on all
        #but the first socket. Even if on self.Peers list.
        
        #RETURNS; True if Peer was found, False if no Peer exists on self.Peers.
        
        for k in self.Peers:
            if k[1][0] == packetTuple[0]:
                conn = k[0]
                break
        else: #The corresponding Peer for this IP could not be found
            return False 
        
        try:        

            try:
                conn.settimeout(1)
                listen = conn.recv(1024)
                if listen != None:
                    print( "Listenned: " + self.evalPacket(listen) )
                return True
            except:
                None
            if packetTuple[1] == '': #was passed an empty packet just to listen
                return True
            try:
                conn.settimeout(.5)
                conn.send(packetTuple[1])
                print("Sent:" + self.evalPacket(packetTuple[1]))
                self.packetStack.pop(0)
                return True
            except:
                self.packetStack.append( self.packetStack.pop(0) )
                raise
            #print("Debug sendPacket(): Should be (destination, finalBytes): %s" % (packetTuple,) )
        except: 
            #This will happen if a peer tries to send to another peer, but hears no response.
            #Regular usage will eventually accumulate missed packets, due to the asyncronous nature of this 
            #algorythm. But a bad peer will accumulate them much faster. And, the cost of a live Peer being 
            #kicked from the Peer list is relatively small. The kick will propogate to the other Live peer
            #and it will attempt a reconnect automatically. A bad peer however will attempt no such reconnect and
            #so it will stop making other sockets with the same IP invisible.
            for k in self.badPeers: #badPeer format: (Peer socket, reject Count)
                if conn == k[0]:
                    k[1] = k[1] + 1
                    break
            else:
                self.badPeers.append( [conn, 1] )
                    
            
#-------------My Error is in this evalPacket Code----------------------------------------------------

    def evalPacket(self, recievedBytes): #I like the idea of passing recievedBytes and returning unpacked string.
        #print("evalPacket Called on:" + recievedBytes.decode('ascii'))
        #That way you can tag it to print("Sent:" + self.evalPacket())
        #recievedBytes should be in form: ( myIP, (state, timeAlive) )
        
        rp = eval(recievedBytes.decode('ascii'))
        
       
        
        
        if rp['head'] == 'msg':
            if  (len(self.stateOfPeers) > 0) and rp[0] in self.stateOfPeers:
                if self.stateOfPeers['rp[0]'][1] < rp[1][1]:
                    self.stateOfPeers[rp[0]] = rp[1]
                    return(  rp[0] + "'s sensor is: " + rp[0][0] )
                else:
                    None
                    #packet recieved was from an earlier state than current value. Sometimes sends out of order
                    #due to necessary behavior of send loop.
            else:
                #Peer not in stateOfPeers yet
                self.stateOfPeers[rp[0]] = rp[1]
                return(  rp[0] + "'s sensor is: " + rp[0][0] )
        elif rp['head'] == 'link':
            return( rp['link'])
        else:
            return("Not a Recognized Packet")        
            
  
    
    def genConfig(self,path):
        if path =='./ServerDefault.conf':
            print("Creating new default server configuration")
        else:
            print("Creating new configuration file")
        f = open(path,'a')
        f.close()
        f = open(path,'w')
        f.write("self.host = ''\n")
        f.write("self.port = " + input("Server port:") + "\n")
        f.write('self.myIP = "' + str( input("IP address on this network:" ) ) + '"\n' )
        f.write('self.baseIP = "' + str( input("Base Network IP (ex: 10.0.0.): ") )  + '"\n' )
        f.write('self.sensorPin = ' + input("Sensor Pin?: ") + '\n' )
        f.write("self.whitelist = ")
        inp = input("Require clients to be on IP list?[y/n]\n")
        if inp == "y" or inp == "Y":
            f.write("True\n")
        else:
            f.write("False\n")
        f.write('self.client = [')
        cltmp = []
        
        while True:
            inp = input('Enter client Ip adress or type "done" to continue\n')
            if (inp == 'Done' or inp == 'done'):
                break
            cltmp.append(inp)
            
        for i in range(len(cltmp)):
            if i != len(cltmp)-1:
                f.write("'"+cltmp[i]+"',")
            else:
                f.write("'"+cltmp[i]+"'")
        f.write(']\n')
        
        inp = input("Would you like to assign names to the entered IP Adresses?[y/n]\n")
        if (inp == 'y') | (inp == 'Y'):
            f.write("self.clientnames = [")
            for i in range(len(cltmp)):
                if i != len(cltmp)-1:
                    f.write('''"''' + input("Name for " + cltmp[i] + ": ") +'''",''')
                else:
                    f.write('''"''' + input("Name for " + cltmp[i] + ": ") + '''"''')
            f.write("]\n")
            
        del cltmp
        f.close()
        print("Config created")
        del f


# #Hidden Server Stuff
# <!--
# 
#     #-----------------------------------------------------------------------------------------
#     def evalbuf(self,buf):
#         rp = eval(buf.decode('ascii'))
#         if rp['head'] == 'msg':
#             print(rp['rdtext'])
#             return(True)
#         elif rp['head'] == 'link':
#             print(rp['link'])
#             return(True)
#         elif rp['head'] == 'pulse':
#             ###
#         else:
#             return(False)
#     #-------------------------------------------------------------------------------------------
#     def monitorConnections(self):
#         while self.live:
#             monitorClients() #go through every out bound connection, every connection accepted() and send appropriately
#             monitorServers() #go through every in bound connectoin, every connection seeked() and recv appropriately
#                         
#                         #Have to break it down like this otherwise, when you first go to start the connections,
#                         #nobody will know when to listen vs send. This keeps recv from hanging indefinately if
#                         #Both machines have decided to keep listening instead of one sending to start the process
#                             #Their executions will be very similiar, just reversing the order in sendPackets()
#             
#                                         
#     def monitorClients(self):
#         if(len.self.packetStack) != 0:
#             loopStack = self.packetStack
#             self.packetStack = []
#             for i in range(len(loopStack)):
#                 if loopStack[0].destination == '*':
#                     #Send this packet to all
#                     for k in self.clients
#     def monitorServers(self):
#                                  
# -->

# #Hidden Client
# <!--
# class Client():
#     def __init__(self,conf = './ClientDefault.conf',host=None):
#         try:
#             config = open(conf,'r')
#         except FileNotFoundError:
#             self.genConfig(conf)
#             config = open(conf,'r')
#         exec(config.read())
#         config.close()
#         if host != None:
#             self.host = host
#         self.inth = threading.Thread(target=self.receivePacket)
#         self.packetstack = []
#         
#     def start(self):
#         self.live = True
#         if self.connect():
#             self.inth.start()
#             
#     def stop(self):
#         self.live = False
#         self.inth.join()
#         print("Client Stopped")
#         
#     def connect(self):
#         self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
#         try:
#             self.sock.connect((self.host,self.port))
#             return(True)
#         except:
#             raise
#             return(False)
#         
#     def receivePacket(self):
#         while self.live:
#             buf = self.sock.recv(9)
#             if (len(buf) > 0) and (buf[0] != 123):
#                 self.sock.send(b'*')
#                 buf = self.sock.recv(int(buf))
#             if (len(buf) > 0) and (buf[0] == 123) and (buf[-1] == 125):
#                 if not self.evalbuf(buf):
#                     print("Unkown Packet Recieved")
#             sys.stdout.flush()    
#             del buf
#             buf = []
#         self.sock.close()
#         
#     def evalbuf(self,buf):
#         rp = eval(buf.decode('ascii'))
#         if rp['head'] == 'msg':
#             print(rp['rdtext'])
#             return(True)
#         elif rp['head'] == 'link':
#             print(rp['link'])
#             return(True)
#         else:
#             return(False)
#             
#     
#     
#     def genConfig(self,path):
#         if path =='./ClientDefault.py':
#             print("Creating new default client configuration")
#         else:
#             print("Creating new configuration file")
#         f = open(path,'a')
#         f.close()
#         f = open(path,'w')
#         f.write("self.host = ''\n")
#         f.write("self.port = " + input("Server port:") + "\n")
#         f.close()
#         print("Config created")
#         del f
# -->

# In[ ]:

sv = Peer();sv.start()
print("Server Started. Let's light this candle")



# In[ ]:





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

# In[1]:

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
        self.sensors = threading.Thread(target=self.monitorWorld)
        self.packetStack = []
        self.messageHistory = []
        self.missLimit = 4
        self.state = 'High'
        self.changed = False
        self.Peers = []
        #Peer list structure: (socket, (ip address, port, sensorState, timeAlive, missedHandshakes))
        self.timeAlive = 0
        
        
    def start(self):
        self.live = True;
        self.accept.start()
        self.seek.start()
        self.conManage.start()
        #self.pdbg.start()
        self.sensors.start()
        
    
    def stop(self):
        self.live = False
        print("Allowing Timeout")
        sys.stdout.flush()
        #self.pdbg.join()
        self.seek.join()
        self.send.join()
        print("Stopped")
    
    def monitorWorld(self):
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
                        newPeer = [s, [ip, self.port, "Low", 0, 0]]
                        #
                        
                        #------------------------Peer list structure: (socket, 
                                                    #(ip address, port, sensorState, timeAlive, missedHandshakes))
                        
                        #bug report: OSError: Errno 113 no route to host
                        self.Peers.append(newPeer)
                        print("New Connection Sought: %s" % (self.Peers[-1][1][0],))
                    except ConnectionRefusedError:
                        if self.debugMode[0]: print("Connection refused on " + ip)
                        None
                    except socket.timeout:
                        if self.debugMode[0]: print("Connection timeout on " + ip)
                        None
                    except OSError:
                        if self.debugMode[0]: print("OS Error, no route to host on " +ip)
                        None 
                    except:
                        print("General SeekErr on:" + ip)
                        raise

    def acceptPeers(self,MaxConnections = 7):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind((self.host,self.port))
            self.sock.settimeout(3)
            self.sock.listen(MaxConnections)
        except OSError:
            print("Address already in use. Port " + str(self.port) + " changed to " + str(self.port + 1))
            print("Please restart")
            #---------------------------------------------------Change
            #until I can make it pretty, just doing this hacky response.
            path = './ServerDefault.conf'
            f = open(path, 'a')
            f.write("self.port = " + str(self.port + 1) )
            f.close()
            
            
            
        while self.live and (len(self.Peers) < MaxConnections):
            try:
                newCon = self.sock.accept()
                self.Peers.append(  [newCon[0], [newCon[1][0], newCon[1][1], "Low", 0, 0]] )
                print("New Connection Accepted:",self.Peers[-1][1][0])
            except socket.timeout:
                if self.debugMode[0]: print("Socket timed out")
                None
               
            except:
                if self.debugMode[0]: print("General AcceptErr")
                raise
            
            sys.stdout.flush()
        self.sock.close()                          
       
    
     
    def monitorConnections(self):
        while self.live:
            self.statePacketManager()
            self.digestMulticast()
            self.distributePackets()
            self.listenPeers()
            self.prunePeers()
            
    def prunePeers(self):
        #badPeers is a list of peers that have missed connections, and how many times that peer has missed its connection
        #self.missLimit is how many times a Peer can miss a transmission before getting kicked
        for k in self.Peers:
            #print(k)
            if k[1][4] > self.missLimit:
                print("Peer " + self.Peers[j][1][0] + " unresponsive. Kicking...")
                self.Peers.remove(k)
                    
            
                    
    def statePacketManager(self):
    #This looks at the current sensor state and adds its value to the packetStack. Its done here in the MonitorConnections()
    #thread in to be sure that packetStack isn't modified by an outside thread during self.distributePackets()
        if self.changed: 
            #each update sent like the following: ( myIP, (state, timeAlive) )
            #So each peer can evaluate what the other sends, and recieve a data structure with its time, IP and its state. Easy to use
            msgContents =  "('" + self.myIP + "', ('" + self.state + "', " + str( self.timeAlive ) + ") )" 
            #self.packetStack.append( MessageStruct( msgContents ,self.myIP, '*' ).finalPacket)
            #print("added Multicast")
            for i in self.Peers:
                if self.debugMode[2]: print("Queueing Packet for " + i[1][0])
                self.packetStack.append( MessageStruct( msgContents ,self.myIP, i[1][0] ).finalPacket)
            self.changed = False       
   

    def digestMulticast(self):        
    
        None
        
        
    def listenPeers(self):
        #Listens for one second to all peers
        for k in self.Peers:
            try:
                k[0].settimeout(1)
                listen = k[0].recv(1024)
                if listen != None:
                    #self.updateInternalModel(listen)
                    print( "Listenned: " + self.evalPacket(listen) )
                k[0].settimeout(.5)
                return True
            
            except socket.timeout:
                #Nothing was heard from this peer
                k[0].settimeout(.5)
                None
            except:
                k[0].settimeout(.5)                
                raise
            
        
    def distributePackets(self):
        #Manages when and where to call sendPacket() to. 
        #if self.debugMode[2]: print("Packet Stack: " + str(self.packetStack) )
        if len(self.Peers) != 0:
            for k in self.Peers:
                if ( len(self.packetStack) != 0) and (self.packetStack[0][0] == k[1][0] ):
                    self.sendPacket(self.packetStack[0])
                    break
            else: #to cycle through dead packets. If you accidentally get a packet with a bad IP.
                try:self.packetStack.append( self.packetStack.pop(0))
                except: None
     

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
                if self.debugMode[2]: print("Attempting: " + k[1][0])
                break
        else: #The corresponding Peer for this IP could not be found
            return False 
        try:
            conn.settimeout(.5)
            conn.send(packetTuple[1])
            if self.debugMode[2]: print("Sent:" + packetTuple[1].decode("UTF-8"))
            self.packetStack.pop(0)
            return True
        except:
            self.packetStack.append( self.packetStack.pop(0) )
            k[1][4] += 1 
            raise
            
            
            #This will happen if a peer tries to send to another peer, but hears no response.
            #Regular usage will eventually accumulate missed packets, due to the asyncronous nature of this 
            #algorythm. But a bad peer will accumulate them much faster. And, the cost of a live Peer being 
            #kicked from the Peer list is relatively small. The kick will propogate to the other Live peer
            #and it will attempt a reconnect automatically. A bad peer however will attempt no such reconnect and
            #so it will stop making other sockets with the same IP invisible.
            
            
#-------------My Error is in this evalPacket Code----------------------------------------------------


#There some fucking keyError going on here. The damnedest thing is though, it works on a clean project.
#Something about it being in a class and dictionaries royally fucks everything. I've decided to do that
#whole restructuring thing. God damn.

    def evalPacket(self, recievedBytes): #I like the idea of passing recievedBytes and returning unpacked string.
        #print("evalPacket Called on:" + recievedBytes.decode('ascii'))
        #That way you can tag it to print("Sent:" + self.evalPacket())
        #recievedBytes should be in form: ( myIP, (state, timeAlive) )
        
        rp = eval(recievedBytes.decode('ascii'))
        if self.debugMode[2]: print(rp)
        dataPacket = eval(rp['rdtext'] )
        if self.debugMode[2]: print(dataPacket)
        #The problem may be that rp is not what I believe
        
        for i in self.Peers:
            if self.debugMode[2]: print(i[1][0] + " matches " + dataPacket[0])
            if i[1][0] == dataPacket[0]: #if IP's match
                if i[1][4] < dataPacket[1][1]:
                    i[1][2] = dataPacket[1][0]
                    i[1][3] = dataPacket[1][1]
                    return(  dataPacket[0] + "'s sensor is: " + str( dataPacket[1][0] ) )
                else: return("Out of Order Packet Processed.")
        
                #packet recieved was from an earlier state than current value. Sometimes sends out of order
        print("unknown Peer in Packet") 
        return None
    
    def genConfig(self,path):
        if path =='./ServerDefault.conf':
            print("Creating new default server configuration")
        else:
            print("Creating new configuration file")
        f = open(path,'a')
        f.close()
        f = open(path,'w')
        f.write("self.host = ''\n")
        f.write("self.port = " + input("Server port: ") + "\n")
        f.write('self.myIP = "' + str( input("IP address on this network: " ) ) + '"\n' )
        f.write('self.baseIP = "' + str( input("Base Network IP (ex: 10.0.0.): ") )  + '"\n' )
        f.write('self.sensorPin = ' + input("Sensor Pin: ") + '\n' )
        inp = input("Start in debug mode: \nWarning: Outputs flood of text in normal usage [y/n]: ")
        f.write("## debugMode list corresponds to the following output: [ Network, Sensors, sendPackets ]\n")
        f.write('self.debugMode = [')
        if inp == "y" or inp == 'Y':
            inp = input("    Network Debug [y/n]: ")
            if inp == "y" or inp == 'Y': f.write(" True, ")
            else: f.write(" False, ")
            inp = input("    Sensor Debug [y/n]: ")
            if inp == "y" or inp == 'Y': f.write(" True, ")
            else: f.write(" False, ")
            inp = input("    Send and Recieve Debug [y/n]: ")
            if inp == "y" or inp == 'Y': f.write(" True ] ")
            else: f.write(" False] ")
        else: f.write(" False, False, False ]")
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




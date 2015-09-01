
# coding: utf-8

# In[1]:

import socket
import threading
import sys
import time
import nmap

#166.170.45.169
#10.0.0.12
#98.202.207.237


# In[2]:

class MessageStruct():
    def __init__(self, text, sender, destination): # intrep = intended recipient
        self.packet= {'head':'msg','rdtext': (text)}
        self.destination = destination
        self.finalbytes = bytes(str(self.packet),"UTF-8")
        self.finalPacket = (destination, self.finalbytes)


# In[3]:

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

# In[4]:

class Peer():
    def __init__(self, conf = './ServerDefault.conf',):
        try:
            config = open(conf,'r')
        except FileNotFoundError:
            self.genConfig(conf)
            config = open(conf,'r')
        exec(config.read())
        config.close()
        self.connections = []
        self.badConnections = []
        self.accept = threading.Thread(target=self.acceptPeers,kwargs={'MaxConnections':7})
        self.seek = threading.Thread(target=self.seekPeers,kwargs={'MaxConnections' :7 })
        #self.pdbg = threading.Thread(target=self.heartbeat,kwargs={'interval':3})
        self.conManage = threading.Thread(target=self.monitorConnections)
        self.stateMachine = threading.Thread(target=self.StMach)
        self.packetStack = [MessageStruct("Everything is up and running!","Server:","*").finalPacket,]
        self.messageHistory = []
        self.state = 'High'
        self.changed = False
        self.Peers = []
    
        
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
        count = 0
        while self.live:
            state = str(count)
            count = count + 1
            time.sleep(2)
            if state != self.state:
                self.state = state
                self.changed = True
                #print("I changed my state: %s" % self.state)
               

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
        while self.live and (len(self.connections) < MaxConnections):
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
            
                    
    def statePacketManager(self):
    #This looks at the current sensor state and adds its value to the packetStack. Its done here in the MonitorConnections()
    #thread in to be sure that packetStack isn't modified by an outside thread during self.distributePackets()
        if self.changed: 
            self.packetStack.append(MessageStruct( self.myIP + "__ My State is:" + str( self.state ) ,self.myIP, "*").finalPacket)
            self.changed = False
            
            
            
   

    def digestMulticast(self):
        #Get's rid "Send to all" packets to remove weird packet Popping errors
        managedStack = []
        #print("Added HeartBeat")
        for i in range(len(self.packetStack) ):
            if self.packetStack[i][0] == '*':
                for k in self.Peers:
                    tempPack = MessageStruct( self.evalPacket(self.packetStack[i][1] ), self.myIP, k[1][0])
                    managedStack.append( tempPack.finalPacket )
            else:
                managedStack.append( self.packetStack[i])
        self.packetStack = managedStack
        #print("PacketStack: %s" % self.packetStack)
        #print("PacketStack Length: %s" % len(self.packetStack))
        
        
    def distributePackets(self):
       
        if len(self.Peers) != 0:
            for k in self.Peers:
                if ( len(self.packetStack) != 0) and (self.packetStack[0][0] == k[1][0] ):
                    self.sendPacket(self.packetStack[0])
                else:
                    self.sendPacket( (k[1][0], '' ))
                
     

    def sendPacket(self, packetTuple):
                           
        #print("Debug sendPacket(): Should be (destination, finalBytes): %s" % (packetTuple,) )
        for k in self.Peers:
            if k[1][0] == packetTuple[0]:
                conn = k[0]
                break
        else: #The corresponding Peer for this IP could not be found
            return False 
        
        try:
            conn.settimeout(1)
            listen = conn.recv(1024)
            if listen != None:
                print( "Listenned: " + self.evalPacket(listen) )
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
 
                
    def evalPacket(self, recievedBytes): #I like the idea of passing recievedBytes and returning unpacked string.
        #print("evalPacket Called on:" + recievedBytes.decode('ascii'))                        #That way you can tag it to print("Sent:" + self.evalPacket())
        rp = eval(recievedBytes.decode('ascii'))
    
        if rp['head'] == 'msg':
            return( rp['rdtext'] )
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
        f.write('self.baseIP = "' + str( input("Base Network IP: (ex: 10.0.0.)") )  + '"\n' )
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

# In[5]:

sv = Peer();sv.start()
print("started!")



# In[ ]:

packetStack = (MessageStruct("Everything is up and running!","Server:","A").finalPacket,)
        


# In[ ]:

type(packetStack)


# In[ ]:

sv.Peers


# In[ ]:

print(sv.messageHistory)


# In[ ]:




# In[ ]:




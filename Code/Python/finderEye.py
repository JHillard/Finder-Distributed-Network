
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
        #Starts every needed thread to run the FinderEye
        self.live = True;
        self.accept.start()
        self.seek.start()
        self.conManage.start()
        self.sensors.start()
        
    
    def stop(self):
        #Stops every thread in FinderEye.
        self.live = False
        print("Allowing Timeout")
        sys.stdout.flush()
        #self.pdbg.join()
        self.seek.join()
        self.send.join()
        print("Stopped")
    
    def monitorWorld(self):
        #Uses it's sensors to look at the outside world. Doesn't try to directly add something to the stack
        #to avoid modifying the packet stack while in use in another thread. Changes FinderEye's internal state
        #to match that of the sensor's, and then changes the flag self.changed to let the other thread know
        
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
        #Seeks other FinderEyes on the network. Only looks through IP addr. XXX.XXX.XX.1 through xx.35
        #When something accepts it's connection, adds it to the Peer list and assign default sensor and life values
        
        while self.live:
            for i in range (1 , 35):
                ip = self.baseIP + str(i)
                for k in self.Peers:
                    if (k[1][0] == ip):  
                        break                    
                else: #Should Only execute when above for loop exits normally IE. we aren't already connected
                    try:
                        if ip == self.myIP: break
                        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                        s.settimeout(.5)
                        s.connect((ip, self.port))
                        s.settimeout(None)
                        newPeer = [s, [ip, self.port, "Low", 0, 0]]
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
        #Accepts incoming connections from seekPeers() on another FinderEye. Gets added to the Peer list.
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind((self.host,self.port))
            self.sock.settimeout(3)
            self.sock.listen(MaxConnections)
        except OSError:
            print("Port " + str(self.port) + " already in use." )
            print("Please change ServerDefault.conf and restart")
            
            
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
        #Monitors the Sensor states, sends appropraite messages from the packet stack, and listens to other Peers
        #will remove unresponsive Peers as well.
        #all done in a single thread in order to be less computationally expensive and keep battery life up.
        while self.live:
            self.statePacketManager()
            self.distributePackets()
            self.listenPeers()
            self.prunePeers()
            
    def prunePeers(self):
        #badPeers is a list of peers that have missed connections, and how many times that peer has missed its connection
        #self.missLimit is how many times a Peer can miss a transmission before getting kicked
        for k in self.Peers:
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
            for i in self.Peers:
                if self.debugMode[2]: print("Queueing Packet for " + i[1][0])
                self.packetStack.append( MessageStruct( msgContents ,self.myIP, i[1][0] ).finalPacket)
            self.changed = False       
        
    def listenPeers(self):
        #Listens for one second to all peers
        for k in self.Peers:
            try:
                k[0].settimeout(1)
                listen = k[0].recv(1024)
                if listen != None:
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
        
        if len(self.Peers) != 0:
            for k in self.Peers:
                if ( len(self.packetStack) != 0) and (self.packetStack[0][0] == k[1][0] ):
                    self.sendPacket(self.packetStack[0])
                    break
            else: #to cycle through dead packets. If you accidentally get a packet with a bad IP.
                try:self.packetStack.append( self.packetStack.pop(0))
                except: None
        #if self.debugMode[2]: print("Packet Stack: " + str(self.packetStack) )

    def sendPacket(self, packetTuple): 
        #given a tuple (ip Destination, finalBytes to send) this method first tries to find the Peer that holds
        #that IP. First listens on that connection for a time, then sends its own. No handshakes involved. It
        #only pops from the packetStack if the message is successfully sent (conn.send() doesn't time out)
        #Uses first instance of IP adddr found. Meaning a device connected multiple times is invisible on all
        #but the first socket. Even if on self.Peers list. Thus the importance of prunePeers()
        
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
            #and it will attempt a reconnect automatically. A bad peer however will attempt no such reconnect
            #and so it will stop making other sockets with the same IP invisible.
            


    def evalPacket(self, recievedBytes):
        #takes in recieved bytes from a transmission and updates the Peers state's accordingly. Returns what
        #Peer's sensor changed so the User can see.
        
        rp = eval(recievedBytes.decode('ascii'))
        if self.debugMode[2]: print(rp)
        dataPacket = eval(rp['rdtext'] )
        if self.debugMode[2]: print(dataPacket)
        
        for i in self.Peers:
            if self.debugMode[2]: print(i[1][0] + " matches " + dataPacket[0])
            if i[1][0] == dataPacket[0]: #if IP's match
                if i[1][4] < dataPacket[1][1]:
                    i[1][2] = dataPacket[1][0]
                    i[1][3] = dataPacket[1][1]
                    return(  dataPacket[0] + "'s sensor is: " + str( dataPacket[1][0] ) )
                else: return("Out of Order Packet Processed.")        
                #packet recieved was from an earlier state than current value. Must sometimes send out of order
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


# In[ ]:

sv = Peer();sv.start()
print("Eyes are exchanging information.\n To complete setup please press Ctrl + C: " )



# In[ ]:




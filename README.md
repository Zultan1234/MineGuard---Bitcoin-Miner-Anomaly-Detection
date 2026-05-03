<img width="761" height="112" alt="image" src="https://github.com/user-attachments/assets/04042fab-7188-4826-8c4e-26cb9104b365" /># MineGuard---Bitcoin-Miner-Anomaly-Detection
A monitoring dashboard for ASIC crypto miners. Tracks hashrate, temperatures, and fan health in real time, learns normal behavior, and alerts you to hardware anomalies before they cause downtime.

------------------------------------------------------------------------------------------------------------------------

In order to setup this tool, please follow the setup steps provided below:

Software was installed using the following:
 - Python 3.13
 - Node.js 18+
 - NPM (comes with Node.js)

They have to be included in PATH for everything to work directly out of the box. Otherwise, you must modify the file start.bat after install. 

#Step 1:
Install the files. It is recommended to isntall the compressed file, then extract it. 
<img width="568" height="93" alt="image" src="https://github.com/user-attachments/assets/ba6edc7a-917f-425d-8bf2-00d4bf259be1" />

#Setup Chatbot (optional):
If you want to setup the chatbot to be integrated within the user interface, go into ..\miner-monitor\backend\data, and create a text file called gemini_key.txt. 

<img width="616" height="185" alt="image" src="https://github.com/user-attachments/assets/f212ca4e-9c89-4b87-8aa8-7adbdf0651bb" />


Got to the website https://aistudio.google.com/api-keys to get a free API key. 
Copy the key and paste it in the gemini_key.txt file, then continue. 

<img width="761" height="112" alt="image" src="https://github.com/user-attachments/assets/1b504ecf-ad5c-4a8f-afbb-05a8ade4f1c5" />



Note that this is optional, however it allows you to use a chatbot that can diagnose your miner using the live data, and give you suggestions.


#Step 2:

Once extracted, enter the new folder miner-monitor, and if all dependancies mentioned above are in PATH, then you can simply run start.bat, if it gives a warning, press run:
<img width="498" height="274" alt="image" src="https://github.com/user-attachments/assets/02df93af-7a64-4ec6-93d5-4e7a69776e4b" />

#Step 4:
This will open a CMD window, and it will install some python packages for you. This might take some time. Do not close the window, and wait until it is done. 

#Step 5:
If the window closes, then just re-run start.bat, and it should start up the server. If you are running into some problems in accessing the server, try setting inbound and outbound rules in Windows Defender Firewall. Set them for both frontend and backend ports 5001 and 5002


<img width="787" height="88" alt="image" src="https://github.com/user-attachments/assets/6b2b9796-3703-4587-8430-70e27b7b915f" />

Make sure that all TCP connections are allowed on these ports to avoid any 


<img width="534" height="436" alt="image" src="https://github.com/user-attachments/assets/b8650609-3203-40a5-a92c-b0ddc9962d70" />


<img width="527" height="429" alt="image" src="https://github.com/user-attachments/assets/1f708869-f687-45e0-ae57-c75dd632ee33" />


<img width="535" height="428" alt="image" src="https://github.com/user-attachments/assets/6a8bad64-4f87-4345-ad1a-797160709f0b" />

#Step 6:
Now, the server is up, and the server must be running on the same netowrk as the crypto-miners, in order to access their API. Therefore, you must know the IP of each miner before hand, or you can find it by entering your rourter and checking for connections. Another way is to use the command: "arp -a" in CMD (only if you used the computer to access the miners beforehand. 

Click: Add miner.

Now for each miner, insert their IP adresses, and for the ports, use their API ports. Most Antminer models use the port 4028, which is the port we used during testing.


<img width="525" height="296" alt="image" src="https://github.com/user-attachments/assets/26476e47-0535-4b83-9ac1-c9530287806a" />


Set the polling frequency to any that you like. We used 15 second windows in testing.


<img width="569" height="389" alt="image" src="https://github.com/user-attachments/assets/bbecde08-8ba0-42d8-8925-f0679a4edb2d" />

After setting up the miner, it should be visible in the dashboard. 

#Training the model:

Now go to the Training tab, and check the training requirements. Make sure your miner is online and collecting data in the dashboard. 

Leave system on for some time, until there us enough data points to tran the model. Usually more than a few thousand is good. 12 hours of data collection is a good amount, howver you can leave it for longer and train it once finished.

#Anomaly detection
After training the model, if it detects an anomaly (irregular data) it will turn yellow. If there is a critical issue, it will turn red. 

#Using the chatbot:
You can use the chat bot for any questions about any miner. It uses data from the API and can diagnose the miner.

#Ayman Taleb
#ID: 60011014


#importing libraries for GPIO, json, time, LCD
import RPi.GPIO as GPIO
import sys
import Adafruit_DHT as DHT
import time
import requests
import json
from datetime import datetime
from pytz import timezone
import pytz
from PCF8574 import PCF8574_GPIO
from Adafruit_LCD1602 import Adafruit_CharLCD


#initializing pins, GPIO settings, HVAC system flags
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
SensorledPin = 18 #led for motion detection
ACledPin = 26 #led for AC
HeatledPin = 19 #led for heater
SIRPin = 17 #pin for motion detection 
incTempPin = 21 #pin to increase temp
decTempPin = 20 #pin to decrease temp
DoorPin = 12 #pin for "door" button
DHT11 = DHT.DHT11 #DHT 11
DHTPin = 23 #pin for DHT
#setting inputs and outputs for GPIO
GPIO.setup(SensorledPin, GPIO.OUT) 
GPIO.setup(ACledPin, GPIO.OUT)
GPIO.setup(HeatledPin, GPIO.OUT)
GPIO.setup(SIRPin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(DoorPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.output(SensorledPin, GPIO.LOW)
GPIO.output(ACledPin, GPIO.LOW)
GPIO.output(HeatledPin, GPIO.LOW)
GPIO.setup(incTempPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(decTempPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
#initializing values used in logic
weather = 0
HVACtemp = 69
doorOpen = False
ambTemp = 0
energyConsumption = 0
energyCost = 0
realHumid = 0

#HVAC modes for logic
#0 = off
#1 = AC
#2 = Heater
HVACmode = 0


#initialize LCD
PCF8574_address = 0x27  # I2C address of the PCF8574 chip.
PCF8574A_address = 0x3F  # I2C address of the PCF8574A chip.
# Create PCF8574 GPIO adapter.
try:
    mcp = PCF8574_GPIO(PCF8574_address)
except:
    try:
        mcp = PCF8574_GPIO(PCF8574A_address)
    except:
        print ('I2C Address Error !')
        exit(1)
# Create LCD, passing in MCP GPIO adapter.
lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4,5,6,7], GPIO=mcp)


#using the CIMIS API we can use json to pull a data request to get the hourly relative humitity in Irvine
def getHumidity():
    timeNow = datetime.now(tz=pytz.utc) #setting day to current day
    timeNow = timeNow.astimezone(timezone('US/Pacific'))
    date = timeNow.strftime('%Y-%m-%d')
    # apiKey =  
    cimisAPIurl = f"https://et.water.ca.gov/api/data?appkey={apiKey}&targets=75&startDate={date}&endDate={date}&dataItems=hly-rel-hum"
    
    r = requests.get(cimisAPIurl) #requesting data specified in url, hly-rel-hum, hourly relative humitity
    r_data = json.loads(r.content)
    records = r_data["Data"]["Providers"][0]["Records"] #this function can break the program because the CIMIS data base doesn't update in time
    for item in records: #pulling humidity
        if item["Date"] == date:
            humid = item["HlyRelHum"]["Value"]
            if humid != 'None':
                return humid
            else:
                return 69

#when infrared sensor detecs motion this is called, turing on the led
def SIR(channel):
    try:
        timer = 10
        while timer > 0:
            GPIO.output(SensorledPin, GPIO.HIGH)
            print("led on\n", timer)
            time.sleep(1)
            timer = timer -1
        GPIO.output(SensorledPin, GPIO.LOW)

    except KeyboardInterrupt:
        GPIO.cleanup()

#reading the data from the DHT 11, getting temp and humidity but only the CIMIS humidity is used for the weather
def DHT_read():
    global ambTemp
    humiDHT, temp = DHT.read(DHT11, DHTPin) #reading temp and humidity 
    if humiDHT is not None and temp is not None:
        tempSum = 0
        humidSum = 0
        for i in range(3): #averaging last three temp readings
            tempSum = ((temp * 1.8) + 32) + tempSum
        realHumid = getHumidity() #getting humidity
#         realHumid = 80
        realHumid = float(realHumid)
        temp = tempSum/3
        ambTemp = temp
        global weather 
        weather = temp + .05*realHumid #getting the feel like weather
        weather = round(weather)
        print("temp = {0:0.1f}F humid = {1:0.1f}%".format(temp,realHumid))
    else:
        print("DHT error")
        
#function to inc desired temp
def inc_HVACtemp(channel):
    global HVACtemp
    HVACtemp = HVACtemp + 1
    print("HVACtemp = ", HVACtemp, "F")
#function to dec desired temp
def dec_HVACtemp(channel):
    global HVACtemp
    HVACtemp = HVACtemp - 1
    print("HVACtemp = ", HVACtemp, "F")



doorNotifevent = None #flag to know if the door open/close message was displayed so it wont over take standard lcd output

#making lcd display door open/closed, takes doorOpen flag to check its status and act acorrdingly
def doorNotif(doorOpen):
    try:
        global doorNotifevent
        if doorOpen:
            mcp.output(3,1)     # turn on LCD backlight
            lcd.begin(16,2)     # set number of LCD lines and columns
            LCDclear()
            lcd.setCursor(0,0)  # set cursor position
            lcd.message('Door Open!')
            doorNotifevent = True
        else:
            mcp.output(3,1)     # turn on LCD backlight
            lcd.begin(16,2)     # set number of LCD lines and columns
            LCDclear()
            lcd.setCursor(0,0)  # set cursor position
            lcd.message('Door Closed!')
            doorNotifevent = True
    except KeyboardInterrupt:
        GPIO.cleanup()
        LCDclear()


#sets door status flag and prints energy/cost
def toggleDoor(channel):
    global doorOpen
    if doorOpen == False:
       doorOpen = True 
       doorNotif(doorOpen)
       energyCost = energyConsumption * 0.5
       print("Energy: ",energyConsumption,"KWh", "Cost: $",energyCost)
    elif doorOpen == True:
        doorOpen = False 
        doorNotif(doorOpen)
        energyCost = energyConsumption * 0.5
        print("Energy: ",energyConsumption,"KWh", "Cost: $",energyCost)

#clearing LCD        
def LCDclear():
    lcd.clear()

GPIO.add_event_detect(SIRPin, GPIO.RISING, callback = SIR, bouncetime = 500)#interrput for motion sensor
GPIO.add_event_detect(incTempPin, GPIO.RISING, callback = inc_HVACtemp, bouncetime = 300)#interrput for inc temp
GPIO.add_event_detect(decTempPin, GPIO.RISING, callback = dec_HVACtemp, bouncetime = 300)#interrput for dec temp
GPIO.add_event_detect(DoorPin, GPIO.RISING, callback = toggleDoor, bouncetime = 100)#interrput for door open


#main loop, try catch for keyboard interrput to clean GPIO and clear LCD
try:
#LCD initialization
    mcp.output(3,1)     # turn on LCD backlight
    lcd.begin(16,2)     # set number of LCD lines and columns
    #main loop, constantly updated LCD and values, detects temp and sets HVAC accordingly
    while True:
        LCDclear()
        lcd.setCursor(0,0)  # set cursor position
        if weather >= HVACtemp + 3:
            HVACmode = 1
        elif weather <= HVACtemp - 3:
            HVACmode = 2
        
        print(doorOpen)
        print(HVACmode)
        if doorOpen == False and HVACmode == 1: #if HVAC mode is 1, it is set to AC, led is set, and checks if the motion sensor light is on and displays its status, displays HVAC temp/weather in F
            energyConsumption = 18
            GPIO.output(ACledPin, GPIO.HIGH)
            GPIO.output(HeatledPin, GPIO.LOW)
            HVACmode = 1
            if GPIO.input(SensorledPin):
                lcd.message('HVAC:AC ' + str(HVACtemp)+'/'+str(weather) + 'F\nL:ON')
            else:
                lcd.message('HVAC:AC ' + str(HVACtemp)+'/'+str(weather) + 'F\nL:OFF')
            print("HVACtemp = ", HVACtemp, "F")
            print("AC ON")
        elif doorOpen == False and HVACmode == 2: #if HVAC mode is 2, it is set to HT for heat, led is set, and checks if the motion sensor light is on and displays its status, displays HVAC temp/weather in F
            energyConsumption = 36
            GPIO.output(HeatledPin, GPIO.HIGH)
            GPIO.output(ACledPin, GPIO.LOW)
            HVACmode = 2
            if GPIO.input(SensorledPin):
                lcd.message('HVAC:HT ' + str(HVACtemp)+'/'+str(weather) + 'F\nL:ON')
            else:
                lcd.message('HVAC:HT ' + str(HVACtemp)+'/'+str(weather) + 'F\nL:OFF')
            print("HVACtemp = ", HVACtemp, "F")
            print("Heat ON")
        elif doorOpen == True: #if HVAC mode is 0, it is turned off, led is set, and checks if the motion sensor light is on and displays its status, displays HVAC temp/weather in F
            GPIO.output(ACledPin, GPIO.LOW)
            GPIO.output(HeatledPin, GPIO.LOW)
            HVACmode = 0
            if GPIO.input(SensorledPin):
                lcd.message('HVAC:OFF\n' + str(HVACtemp)+'/'+str(weather) + 'F L:ON')
            else:
                lcd.message('HVAC:OFF\n' + str(HVACtemp)+'/'+str(weather) + 'F L:OFF')
            print("Door Open! HVAC OFF")
        #bounds HVAC temp between 65 and 85
        if HVACtemp < 65:
            HVACtemp = 65
        elif HVACtemp > 85:
            HVACtemp = 85
        #reading from DHT
        DHT_read()
        print("feels like: {0:0.1f}F".format(weather))
        time.sleep(1)
except KeyboardInterrupt:
    GPIO.cleanup()
    LCDclear()
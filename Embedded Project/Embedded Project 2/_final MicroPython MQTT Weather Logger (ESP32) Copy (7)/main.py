import machine
import os
import time
import network
from machine import Pin, ADC
import socket
import uos
import ssd1306  # مكتبة شاشة SSD1306

# معلمات ThingSpeak
THINGSPEAK_WRITE_API_KEY = "K9ANCT215BYGFOBC"  # استبدل بـ API Key الخاص بك
THINGSPEAK_HOST = "api.thingspeak.com"
THINGSPEAK_URL = "/update"

# حساس رطوبة التربة
soil_moisture_pin = ADC(Pin(36))  # ADC1_CH0
soil_moisture_pin.atten(ADC.ATTN_11DB)  # المدى الكامل: من 0 إلى 3.3 فولت

# دبابيس الري
relay = Pin(26, Pin.OUT)
relay.off()  # بدءًا من إيقاف تشغيل الري

# دبابيس LED
led = Pin(27, Pin.OUT)  # LED مدمج أو LED خارجي
led.off()  # بدءًا من إيقاف تشغيل LED

# إعداد بطاقة SD
sd_cs = Pin(15, Pin.OUT)  # دبابيس CS لبطاقة SD (استخدم Pin 15 أو حسب اختيارك)
spi = machine.SPI(1, baudrate=1000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(23), miso=Pin(19))

# محاولة تهيئة بطاقة SD باستخدام machine.SDCard
try:
    sd = machine.SDCard(slot=2, cs=sd_cs)  # slot=2 أو 1 حسب الجهاز الخاص بك
    vfs = uos.VfsFat(sd)
    uos.mount(vfs, '/sd')  # تهيئة بطاقة SD
    print("SD Card mounted successfully!")
except Exception as e:
    print("Error initializing SD card:", e)
    sd = None

# فتح ملف لتخزين البيانات
if sd:
    log_file = open('/sd/soil_data.txt', 'a')  # 'a' تعني إضافة البيانات إلى الملف بدلاً من مسحها
else:
    log_file = None

# الاتصال بالشبكة اللاسلكية
print("Connecting to WiFi", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')  # استبدل باسم الشبكة وكلمة المرور
while not sta_if.isconnected():
    print(".", end="")
    time.sleep(0.1)
print(" Connected!")

# تهيئة شاشة SSD1306
i2c = machine.I2C(0, scl=Pin(22), sda=Pin(21))  # تأكد من تعديل الدبابيس حسب التوصيلات
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# إرسال البيانات إلى ThingSpeak
def send_to_thingspeak(moisture_value, relay_status, led_status):
    print(f"Sending to ThingSpeak: Moisture={moisture_value}, Relay={relay_status}, LED={led_status}")
    
    payload = "api_key={}&field1={}&field2={}&field3={}".format(
        THINGSPEAK_WRITE_API_KEY, moisture_value, relay_status, led_status)
    
    addr = socket.getaddrinfo(THINGSPEAK_HOST, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    
    request = "GET {}?{} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n".format(
        THINGSPEAK_URL, payload, THINGSPEAK_HOST)
    
    s.send(request.encode())
    response = s.recv(1024)
    print("ThingSpeak Response:", response)
    s.close()

# إرسال البيانات إلى SD
def log_to_sd(moisture_value, relay_status, led_status):
    if log_file:
        log_file.write("Moisture: {}, Relay: {}, LED: {}\n".format(moisture_value, relay_status, led_status))
        log_file.flush()  # ضمان كتابة البيانات مباشرة إلى الملف
    else:
        print("SD Card not available. Skipping data logging.")

# تحديث شاشة SSD1306
def update_oled(moisture_value, relay_status, led_status):
    oled.fill(0)  # مسح الشاشة
    oled.text("Moisture: {}".format(moisture_value), 0, 0)
    oled.text("Relay: {}".format(relay_status), 0, 20)
    oled.text("LED: {}".format(led_status), 0, 40)
    oled.show()  # تحديث العرض على الشاشة

# إرسال البيانات إلى ThingSpeak وتخزينها في ملف
prev_moisture = -1
while True:
    moisture_value = soil_moisture_pin.read()
    print("Soil Moisture Value:", moisture_value)

    # تشغيل/إيقاف الري وLED بناءً على مستوى الرطوبة
    if moisture_value < 1500:
        relay.on()
        led.on()
        relay_status = 1
        led_status = 1
    else:
        relay.off()
        led.off()
        relay_status = 0
        led_status = 0

    # إرسال البيانات إلى ThingSpeak وتخزينها في ملف
    if moisture_value != prev_moisture:
        send_to_thingspeak(moisture_value, relay_status, led_status)
        log_to_sd(moisture_value, relay_status, led_status)
        update_oled(moisture_value, relay_status, led_status)
        prev_moisture = moisture_value

    time.sleep(15)  # تحديث كل 15 ثانية

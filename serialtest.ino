void setup()
{
    Serial.begin(115200);
}

void loop()
{

    if (Serial.available())
    {
        char byteRead = Serial.read();
        // when byte recieved light up built in LED pin 13
        if (byteRead == '1')
        {
            digitalWrite(LED_BUILTIN, HIGH);
            Serial.println("LED ON");
        }
        else if (byteRead == '0')
        {
            digitalWrite(LED_BUILTIN, LOW);
            Serial.println("LED OFF");
        }
    }
}
void setup()
{
    Serial.begin(115200);
}

void loop()
{

    if (Serial.available())
    {
        char byteRead = Serial.read();
        Serial.print("Byte read: ");
        Serial.println(byteRead);
    }
}
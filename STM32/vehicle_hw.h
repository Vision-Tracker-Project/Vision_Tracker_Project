#ifndef VEHICLE_HW_H
#define VEHICLE_HW_H
#include <stdint.h>
void Vehicle_HW_Init(void);
void Vehicle_HW_Poll(void);
void Vehicle_RX_ISR(uint32_t status, uint8_t byte);
void Vehicle_Servo_Command(unsigned target, unsigned angle);
#endif

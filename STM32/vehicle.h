#ifndef VEHICLE_H
#define VEHICLE_H
#include <stdint.h>
#ifndef VEHICLE_WATCHDOG_MS
#define VEHICLE_WATCHDOG_MS 250u
#endif
#ifndef VEHICLE_REVERSE_MS
#define VEHICLE_REVERSE_MS 100u
#endif
#ifndef VEHICLE_RAMP_PER_SECOND
#define VEHICLE_RAMP_PER_SECOND 100u
#endif
typedef struct {
    int target[2], output[2], last_sign[2];
    uint32_t zero_since[2], updated, tick;
    unsigned credit;
    int valid;
} Vehicle;
typedef struct { uint8_t bytes[8]; unsigned count; } PacketParser;
typedef void (*ServoHandler)(unsigned target, unsigned angle);
void Vehicle_Init(Vehicle *v, uint32_t now);
void Vehicle_Stop(Vehicle *v);
void Vehicle_Command(Vehicle *v, int left, int right, uint32_t now);
void Vehicle_Tick(Vehicle *v, uint32_t now);
/* Returns 1 for a vehicle frame, 2 for servo, 0 for incomplete/invalid input. */
int Packet_Feed(PacketParser *p, Vehicle *v, uint8_t byte, uint32_t now, ServoHandler servo);
#endif

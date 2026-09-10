#include "device_driver.h"
#include "vehicle.h"
#include "vehicle_hw.h"

#ifndef VEHICLE_PWM_HZ
#define VEHICLE_PWM_HZ 20000u
#endif
#ifndef VEHICLE_LEFT_INVERT
#define VEHICLE_LEFT_INVERT 0
#endif
#ifndef VEHICLE_RIGHT_INVERT
#define VEHICLE_RIGHT_INVERT 0
#endif
#if VEHICLE_PWM_HZ < 1000 || VEHICLE_PWM_HZ > 20000
#error Vehicle PWM must be 1..20 kHz
#endif
static volatile uint32_t milliseconds;
static volatile unsigned head, tail, rx_fault;
static uint8_t rx[128];
static uint32_t rx_time[128];
static Vehicle vehicle;
static PacketParser parser;
static volatile uint32_t watchdog_updated;
static volatile int watchdog_valid;
static unsigned servo_target, servo_angle;

static void defer_servo(unsigned target, unsigned angle) {
    servo_target = target; servo_angle = angle;
}

/* Integration hook: override in servo branch; called only from main context. */
__attribute__((weak)) void Vehicle_Servo_Command(unsigned target, unsigned angle) {
    (void)target; (void)angle;
}
static void apply(void) {
    static int previous_l = 999, previous_r = 999;
    int l = vehicle.output[0] * (VEHICLE_LEFT_INVERT ? -1 : 1);
    int r = vehicle.output[1] * (VEHICLE_RIGHT_INVERT ? -1 : 1);
    unsigned pins = (l > 0 ? 1u << 2 : l < 0 ? 1u << 3 : 0)
                  | (r > 0 ? 1u << 4 : r < 0 ? 1u << 5 : 0);
    if (l == previous_l && r == previous_r) return;
    previous_l = l; previous_r = r;
    /* Gate both enables before direction writes. Load both preloads together. */
    TIM3->CCER = 0;
    GPIOC->BSRR = ((0x3Cu & ~pins) << 16) | pins;
    TIM3->CR1 |= 1u << 1; /* UDIS: no overflow between CCR writes */
    TIM3->CCR1 = (l < 0 ? -l : l) * (TIM3->ARR + 1) / 100;
    TIM3->CCR2 = (r < 0 ? -r : r) * (TIM3->ARR + 1) / 100;
    TIM3->CR1 &= ~(1u << 1);
    TIM3->EGR = 1;
    TIM3->CCER = (1u << 0) | (1u << 4);
}
void SysTick_Handler(void) {
    ++milliseconds;
    /* Hardware cutoff also survives a stalled main loop. */
    if (!watchdog_valid || milliseconds - watchdog_updated >= VEHICLE_WATCHDOG_MS) {
        TIM3->CCER = 0;
        TIM3->CCR1 = TIM3->CCR2 = 0;
    }
}
void Vehicle_RX_ISR(uint32_t status, uint8_t byte) {
    unsigned next = (head + 1) & 127u;
    if (status & 15u || next == tail) { rx_fault = 1; return; }
    if (status & (1u << 5)) {
        rx[head] = byte; rx_time[head] = milliseconds; head = next;
    }
}
void Vehicle_HW_Init(void) {
    unsigned pin;
    RCC->AHB1ENR |= 1u << 2;
    RCC->APB1ENR |= 1u << 1;
    (void)RCC->AHB1ENR;
    GPIOC->BSRR = 0xFCu << 16;
    for (pin = 2; pin <= 7; ++pin) {
        GPIOC->MODER = (GPIOC->MODER & ~(3u << (pin * 2))) | ((pin < 6 ? 1u : 2u) << (pin * 2));
        GPIOC->OTYPER &= ~(1u << pin);
        GPIOC->PUPDR = (GPIOC->PUPDR & ~(3u << (pin * 2))) | (2u << (pin * 2));
    }
    GPIOC->AFR[0] = (GPIOC->AFR[0] & ~0xFF000000u) | 0x22000000u;
    TIM3->CR1 = 0; TIM3->CCER = 0;
    TIM3->PSC = 0; TIM3->ARR = TIMXCLK / VEHICLE_PWM_HZ - 1;
    TIM3->CCMR1 = (6u << 4) | (1u << 3) | (6u << 12) | (1u << 11);
    TIM3->CCR1 = TIM3->CCR2 = 0;
    TIM3->EGR = 1; TIM3->CR1 = (1u << 7) | 1;
    Vehicle_Init(&vehicle, 0);
    SysTick_Config(HCLK / 1000);
}
void Vehicle_HW_Poll(void) {
    unsigned budget = 128;
    while (budget--) {
        uint8_t byte;
        uint32_t received;
        uint32_t mask = __get_PRIMASK();
        __disable_irq();
        if (rx_fault) {
            tail = head; rx_fault = 0; parser.count = 0;
            vehicle.tick = milliseconds; Vehicle_Stop(&vehicle); apply();
        }
        if (head == tail) { __set_PRIMASK(mask); break; }
        byte = rx[tail]; received = rx_time[tail]; tail = (tail + 1) & 127u;
        if (milliseconds - received >= VEHICLE_WATCHDOG_MS) {
            parser.count = 0; vehicle.tick = milliseconds;
            Vehicle_Stop(&vehicle); apply();
            __set_PRIMASK(mask); continue;
        }
        __set_PRIMASK(mask);
        /* Parser and command publication serialized with watchdog interrupt. */
        __disable_irq();
        if (Packet_Feed(&parser, &vehicle, byte, milliseconds, defer_servo) == 1) {
            /* Watchdog uses wire arrival; reversal wait uses physical apply time. */
            vehicle.updated = received;
            apply();
        }
        watchdog_updated = vehicle.updated; watchdog_valid = vehicle.valid;
        __set_PRIMASK(mask);
        if (servo_target) {
            Vehicle_Servo_Command(servo_target, servo_angle); servo_target = 0;
        }
    }
    {
        uint32_t mask = __get_PRIMASK();
        __disable_irq();
        Vehicle_Tick(&vehicle, milliseconds); apply();
        __set_PRIMASK(mask);
    }
}

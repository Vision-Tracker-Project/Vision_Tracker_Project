#include "device_driver.h"
#include <stdio.h>

extern volatile uint8_t g_rx_packet[PACKET_SIZE];
extern volatile uint8_t g_packet_ready; // 메인 루프로 보낼 완료 신호

static void Sys_Init(int baud)
{
    SCB->CPACR |= (0x3 << 10 * 2) | (0x3 << 11 * 2);
    Clock_Init();
    Uart2_Init(baud);
    setvbuf(stdout, NULL, _IONBF, 0);
    LED_Init();
}

void Main(void)
{
    Sys_Init(115200);
    TIM2_Servo_Init();
    Uart2_RX_Interrupt_Enable(1);

    // TIM2_Servo_Set_Pan_Angle(90);
    // TIM2_Servo_Set_Tilt_Angle(90);

    for (;;)
    {
        if (g_packet_ready)
        {
            g_packet_ready = 0; // 플래그 초기화

            uint8_t target = g_rx_packet[1];
            uint8_t action = g_rx_packet[2];
            uint8_t param  = g_rx_packet[3];

            switch (target)
            {
                case 0x01: // 서보 모터 1번 (팬)
                    TIM2_Servo_Set_Pan_Angle(param);
                    break;

                case 0x02: // 서보 모터 2번 (틸트)
                    TIM2_Servo_Set_Tilt_Angle(param);
                    break;

                // case 0x03: // GPIO / LED 제어
                //     LED_Set(action);
                //     break;

                default:
                    break;
            }
        }
    }
}

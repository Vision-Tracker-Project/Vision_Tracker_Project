#include "device_driver.h"

volatile uint8_t g_rx_packet[PACKET_SIZE];
volatile uint8_t g_packet_ready = 0; // 메인 루프로 보낼 완료 신호
static uint8_t s_rx_index = 0;

void _Invalid_ISR(void)
{
	unsigned int r = Macro_Extract_Area(SCB->ICSR, 0x1ff, 0);
	printf("\nInvalid_Exception: %d!\n", r);
	printf("Invalid_ISR: %d!\n", r - 16);
	for(;;);
}

void USART2_IRQHandler(void)
{
    if (USART2->SR & (1 << 5)) // RXNE 확인
    {
        uint8_t byte = (uint8_t)(USART2->DR & 0xFF);

        // 1. 헤더 동기화 및 바이트 적재
        if (s_rx_index == 0)
        {
            if (byte == PACKET_HEADER) g_rx_packet[s_rx_index++] = byte;
        }
        else if (s_rx_index < PACKET_SIZE)
        {
            g_rx_packet[s_rx_index++] = byte;

            // 2. 6바이트가 모두 찼을 때 검증
            if (s_rx_index == PACKET_SIZE)
            {
                uint8_t checksum = (g_rx_packet[1] + g_rx_packet[2] + g_rx_packet[3]) & 0xFF;
                
                // 테일과 체크섬이 모두 맞으면 깃발 세우기
                if ((g_rx_packet[5] == PACKET_TAIL) && (g_rx_packet[4] == checksum))
                {
                    g_packet_ready = 1; 
                }
                s_rx_index = 0; // 다음 수신 준비
            }
        }
    }
}
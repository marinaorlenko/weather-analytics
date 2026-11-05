"""Публичный интерфейс пакета интеграции с Open-Meteo.

Пакет объединяет HTTP-транспорт, геокодирование и получение
погодных данных. Внешние компоненты приложения должны
использовать OpenMeteoClient, не обращаясь к внутренним
классам реализации.
"""

from weather_analytics.api.client import OpenMeteoClient

__all__ = ['OpenMeteoClient']

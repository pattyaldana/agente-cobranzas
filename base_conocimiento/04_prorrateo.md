---
tema: prorrateo
categoria: facturacion
titulo: Qué es el prorrateo y cuándo se aplica
palabras_clave: [prorrateo, dias activos, calculo proporcional]
---

# Prorrateo

El prorrateo es el cálculo proporcional de un cargo según la cantidad de
días en que un servicio o condición estuvo realmente vigente, en vez de
cobrar el monto completo del periodo.

## Fórmula general

```
monto_prorrateado = (monto_completo / dias_totales_del_periodo) x dias_aplicables
```

## Casos en los que se usa el prorrateo

- **Alta de servicio a mitad de ciclo**: si un cliente activa su línea el
  día 15 de un ciclo de 30 días, ese primer recibo solo cobra el cargo fijo
  proporcional a los 15 días restantes del ciclo, no el mes completo.
- **Baja o cambio de plan a mitad de ciclo**: si el cliente cambia de plan
  o da de baja el servicio antes de que termine el ciclo, el cargo fijo se
  calcula solo por los días en que estuvo en ese plan.
- **Suspensiones**: como se explica en el documento sobre facturación con
  suspensiones, los días sin servicio activo no se cobran a tarifa completa.
- **Upgrades o downgrades de plan**: si el cliente cambia a un plan más
  caro o más barato a mitad de ciclo, cada tramo (antes y después del
  cambio) se prorratea con su propia tarifa.

## Qué NO se prorratea

El consumo variable (datos adicionales, llamadas fuera de plan, compras de
paquetes) no se prorratea, porque ya representa un uso real y específico —
el prorrateo solo aplica a cargos fijos que se cobran "por el tiempo que
dura algo", no a consumos puntuales.

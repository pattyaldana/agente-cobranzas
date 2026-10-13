---
tema: financiamiento_servicio
categoria: financiamiento
titulo: Financiamiento de deuda del servicio y reglas de simulación
palabras_clave: [financiamiento, cuotas, simulacion, deuda, fraccionamiento]
---

# Financiamiento de la deuda del servicio

Cuando un cliente tiene una deuda pendiente por su servicio de
telecomunicaciones, puede solicitar financiarla en cuotas en vez de pagarla
de una sola vez. El número máximo de cuotas disponible depende del monto de
la deuda.


## Reglas de financiamiento por monto

| Rango de deuda | Cuotas máximas disponibles |
|---|---|
| Menor a S/ 50 | No aplica financiamiento (el monto es muy bajo para fraccionar) |
| S/ 50 a S/ 300 | Hasta 3 cuotas |
| S/ 301 a S/ 800 | Hasta 6 cuotas |
| Mayor a S/ 800 | Hasta 12 cuotas |

El cliente puede elegir cualquier número de cuotas igual o menor al máximo
permitido para su rango (por ejemplo, si su deuda califica para 12 cuotas,
también puede pedir 6 o 3 si así lo prefiere).

## Cómo se calcula cada cuota

Para esta simulación no se aplica interés: cada cuota es el monto total de
la deuda dividido entre el número de cuotas elegido.

```
monto_por_cuota = deuda_total / numero_de_cuotas
```

Ejemplo: una deuda de S/ 600 financiada en 6 cuotas resulta en 6 cuotas de
S/ 100 cada una, que se cargan una por una en los siguientes recibos del
cliente.

## Condiciones generales

- El financiamiento aplica sobre la deuda ya facturada (recibos vencidos o
  por vencer), no sobre consumos futuros aún no facturados.
- Mientras el cliente tiene cuotas de financiamiento pendientes, estas
  aparecen como un concepto adicional en su recibo mensual, junto con el
  consumo normal del periodo.
- Si el cliente no paga una cuota del financiamiento, esa cuota se trata
  como cualquier otro monto vencido: puede generar mora y activar el
  proceso de cobranza.

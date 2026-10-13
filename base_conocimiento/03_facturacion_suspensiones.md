---
tema: calculo_suspensiones
categoria: facturacion
titulo: Cómo se calcula el monto facturado cuando hay suspensiones
palabras_clave: [suspension, corte, reconexion, prorrateo, facturacion parcial]
---

# Cálculo del monto facturado cuando hay suspensiones

Un servicio puede suspenderse durante el ciclo de facturación por distintos
motivos: falta de pago, suspensión voluntaria solicitada por el cliente, o
una suspensión temporal por otras razones administrativas. Esto afecta
cuánto se le cobra al cliente ese periodo.

## Qué pasa con el cargo fijo del plan

El cargo fijo mensual del plan no se cobra completo si el servicio estuvo
suspendido parte del ciclo — se prorratea según los días que el servicio
estuvo realmente activo.

```
cargo_fijo_del_periodo = (cargo_fijo_mensual / dias_del_ciclo) x dias_activo
```

Ejemplo: un plan de S/ 90 al mes, en un ciclo de 30 días, donde el cliente
estuvo suspendido 10 días (activo 20 días):

```
cargo_fijo_del_periodo = (90 / 30) x 20 = S/ 60
```

## Qué pasa con el consumo adicional

El consumo adicional (datos, minutos adicionales, etc.) solo se cobra por lo
efectivamente usado mientras el servicio estuvo activo — no se prorratea,
porque ya refleja uso real.

## Cargos que sí pueden aparecer por la suspensión

- **Cargo por reconexión**: si la suspensión fue por falta de pago, al
  reactivar el servicio puede aplicarse un cargo fijo de reconexión,
  independiente del prorrateo del plan. El cargo actual por reconexión es de S/ 10.

## Suspensión voluntaria

Si el cliente pidió la suspensión voluntariamente (por ejemplo, un viaje
largo), generalmente no se genera cargo por reconexión al reactivar, pero
el prorrateo del cargo fijo funciona igual: solo se cobran los días en que
el servicio estuvo activo.

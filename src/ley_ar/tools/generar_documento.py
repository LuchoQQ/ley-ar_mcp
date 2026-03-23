from __future__ import annotations

from ley_ar.services.document_generator import generar_documento as _generar


def generar_documento(
    tipo: str,
    datos_trabajador: dict,
    datos_empleador: dict,
    datos_caso: dict,
    calculo: dict = None,
) -> dict:
    """Genera un documento legal completo listo para revision y envio.

    Tipos disponibles:
    - "telegrama_registro": Telegrama intimando registro (art. 11 Ley 24.013)
    - "carta_documento": Carta documento reclamando indemnizacion
    - "liquidacion": Planilla de liquidacion detallada

    Args:
        tipo: Tipo de documento a generar
        datos_trabajador: { nombre, cuil, domicilio }
        datos_empleador: { razon_social, cuit, domicilio }
        datos_caso: { fecha_ingreso, fecha_egreso, remuneracion, causa, lugar }
        calculo: Output de calcular_indemnizacion (requerido para carta_documento y liquidacion)
    """
    return _generar(tipo, datos_trabajador, datos_empleador, datos_caso, calculo)

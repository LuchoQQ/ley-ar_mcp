"""
Generador de documentos legales a partir de templates y datos estructurados.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"


def _simple_render(template_text: str, context: dict) -> str:
    """Renderiza un template con sintaxis {{ var }} y bloques {% for/if %}."""
    result = template_text

    def resolve_if(match):
        var_name = match.group(1).strip()
        content = match.group(2)
        if context.get(var_name):
            return content
        return ""

    result = re.sub(
        r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}',
        resolve_if,
        result,
        flags=re.DOTALL,
    )

    def resolve_for(match):
        var_name = match.group(1).strip()
        list_name = match.group(2).strip()
        body = match.group(3)
        items = context.get(list_name, [])
        if not isinstance(items, list):
            return ""
        parts = []
        for item in items:
            rendered = body
            if isinstance(item, dict):
                for k, v in item.items():
                    rendered = rendered.replace("{{ " + f"{var_name}.{k}" + " }}", str(v))
            else:
                rendered = rendered.replace("{{ " + var_name + " }}", str(item))
            parts.append(rendered)
        return "".join(parts)

    result = re.sub(
        r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
        resolve_for,
        result,
        flags=re.DOTALL,
    )

    for key, value in context.items():
        if not isinstance(value, (list, dict)):
            result = result.replace("{{ " + key + " }}", str(value))

    return result


def generar_documento(
    tipo: str,
    datos_trabajador: dict,
    datos_empleador: dict,
    datos_caso: dict,
    calculo: dict = None,
) -> dict:
    """Genera un documento legal completo a partir de datos estructurados.

    Args:
        tipo: "telegrama_registro", "carta_documento", "liquidacion"
        datos_trabajador: { nombre, cuil, domicilio }
        datos_empleador: { razon_social, cuit, domicilio }
        datos_caso: { fecha_ingreso, fecha_egreso, remuneracion, causa, lugar, ... }
        calculo: Output de calcular_indemnizacion (opcional para telegrama, requerido para carta/liquidacion)
    """
    template_map = {
        "telegrama_registro": "telegrama_registro.txt",
        "carta_documento": "carta_documento_despido.txt",
        "liquidacion": "liquidacion_final.txt",
    }

    if tipo not in template_map:
        return {"error": f"Tipo de documento no soportado: {tipo}. Valores: {list(template_map.keys())}"}

    template_path = TEMPLATES_DIR / template_map[tipo]
    if not template_path.exists():
        return {"error": f"Template no encontrado: {template_path}"}

    template_text = template_path.read_text(encoding="utf-8")

    hoy = date.today()
    context = {
        "trabajador_nombre": datos_trabajador.get("nombre", "[NOMBRE]"),
        "trabajador_cuil": datos_trabajador.get("cuil", "[CUIL]"),
        "trabajador_domicilio": datos_trabajador.get("domicilio", "[DOMICILIO]"),
        "empleador_razon_social": datos_empleador.get("razon_social", "[RAZON SOCIAL]"),
        "empleador_cuit": datos_empleador.get("cuit", "[CUIT]"),
        "empleador_domicilio": datos_empleador.get("domicilio", "[DOMICILIO]"),
        "fecha": hoy.strftime("%d/%m/%Y"),
        "fecha_emision": hoy.strftime("%d/%m/%Y"),
        "lugar": datos_caso.get("lugar", "[CIUDAD]"),
        "fecha_ingreso": datos_caso.get("fecha_ingreso", "[FECHA INGRESO]"),
        "fecha_egreso": datos_caso.get("fecha_egreso", "[FECHA EGRESO]"),
        "remuneracion": f"{datos_caso.get('remuneracion', 0):,.0f}",
    }

    causa_map = {
        "sin_causa": "incausado",
        "con_causa": "con invocacion de causa",
        "indirecto": "indirecto (despido indirecto)",
    }
    context["tipo_despido"] = causa_map.get(datos_caso.get("causa", ""), datos_caso.get("causa", ""))
    context["causa"] = datos_caso.get("causa", "sin_causa")
    context["cct"] = datos_caso.get("cct", "")

    advertencias = []

    if tipo in ("carta_documento", "liquidacion") and calculo:
        rubros = []
        for key, rubro in calculo.get("rubros_inmediatos", {}).items():
            if rubro["monto"] > 0:
                rubros.append({
                    "nombre": key.replace("_", " ").title(),
                    "fundamento": rubro["fundamento"],
                    "calculo": rubro["calculo"],
                    "monto": f"{rubro['monto']:,.0f}",
                })
        context["rubros"] = rubros
        context["rubros_inmediatos"] = rubros
        context["subtotal"] = calculo.get("totales", {}).get("inmediatos_formateado", "$0")
        context["total_inmediatos"] = calculo.get("totales", {}).get("inmediatos_formateado", "$0")

        rubros_int = []
        for key, rubro in calculo.get("rubros_requiere_intimacion", {}).items():
            rubros_int.append({
                "nombre": key.replace("_", " ").title(),
                "fundamento": rubro["fundamento"],
                "calculo": rubro["calculo"],
                "monto": f"{rubro['monto']:,.0f}",
                "monto_potencial": f"{rubro.get('monto_potencial', 0):,.0f}" if rubro.get("monto_potencial") else "",
            })
        context["rubros_intimacion"] = rubros_int if rubros_int else None
        context["total_intimacion"] = f"${calculo.get('totales', {}).get('requiere_intimacion', 0):,.0f}"

        apercs = []
        for key, rubro in calculo.get("rubros_apercibimiento", {}).items():
            if rubro["monto"] > 0:
                apercs.append({
                    "nombre": key.replace("_", " ").title(),
                    "fundamento": rubro["fundamento"],
                    "calculo": rubro["calculo"],
                    "monto": f"{rubro['monto']:,.0f}",
                })
        context["apercibimientos"] = apercs if apercs else None
        context["rubros_apercibimiento"] = apercs if apercs else None
        context["total_apercibimiento"] = f"${calculo.get('totales', {}).get('apercibimiento', 0):,.0f}"

        intereses = calculo.get("intereses")
        if intereses and intereses.get("monto_intereses", 0) > 0:
            context["tiene_intereses"] = True
            context["intereses"] = {
                "monto_base": f"{intereses['monto_base']:,.0f}",
                "monto_intereses": f"{intereses['monto_intereses']:,.0f}",
                "monto_con_intereses": f"{intereses['monto_con_intereses']:,.0f}",
                "fecha_desde": intereses["fecha_desde"],
                "fecha_hasta": intereses["fecha_hasta"],
                "dias_totales": str(intereses["dias_totales"]),
            }
            context["monto_intereses"] = f"{intereses['monto_intereses']:,.0f}"
            context["total_con_intereses"] = f"{intereses['monto_con_intereses']:,.0f}"
            context["fecha_calculo"] = intereses["fecha_hasta"]
        else:
            context["tiene_intereses"] = False

        ant = calculo.get("antiguedad", {})
        context["antiguedad_anos"] = str(ant.get("anos", 0))
        context["antiguedad_meses"] = str(ant.get("meses_restantes", 0))
        context["periodos"] = str(ant.get("periodos_indemnizatorios", 0))

        context["advertencias"] = calculo.get("advertencias", [])

    elif tipo in ("carta_documento", "liquidacion") and not calculo:
        advertencias.append("No se proporciono calculo de indemnizacion. El documento tendra campos incompletos.")

    for field, label in [("nombre", "nombre del trabajador"), ("cuil", "CUIL"), ("domicilio", "domicilio del trabajador")]:
        if not datos_trabajador.get(field):
            advertencias.append(f"Falta {label} - completar antes de enviar")
    for field, label in [("razon_social", "razon social"), ("cuit", "CUIT"), ("domicilio", "domicilio del empleador")]:
        if not datos_empleador.get(field):
            advertencias.append(f"Falta {label} del empleador - completar antes de enviar")

    texto = _simple_render(template_text, context)

    return {
        "texto_completo": texto,
        "tipo": tipo,
        "advertencias": advertencias,
        "nota": "Este documento es un borrador orientativo. Debe ser revisado y ajustado por un abogado antes de su envio.",
    }

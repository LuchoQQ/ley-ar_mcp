from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ley_ar.data_manager import ensure_data_ready
from ley_ar.services.legislation_store import LegislationStore
from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch
from ley_ar.services.modificaciones_service import ModificacionesService
from ley_ar.tools.norma_vigente import norma_vigente as _norma_vigente
from ley_ar.tools.calcular_indem import calcular_indemnizacion as _calcular_indemnizacion
from ley_ar.tools.verificar_prescrip import verificar_prescripcion as _verificar_prescripcion
from ley_ar.tools.verificar_prescrip import consultar_plazos_procesales as _consultar_plazos_procesales
from ley_ar.tools.buscar_articulos import buscar_articulos as _buscar_articulos
from ley_ar.tools.jurisprudencia import jurisprudencia as _jurisprudencia
from ley_ar.tools.consultar_cct import consultar_cct as _consultar_cct
from ley_ar.tools.analizar_caso import analizar_caso as _analizar_caso
from ley_ar.tools.generar_documento import generar_documento as _generar_documento
from ley_ar.tools.calcular_intereses import calcular_intereses as _calcular_intereses
from ley_ar.tools.obtener_fallo import obtener_fallo as _obtener_fallo
from ley_ar.tools.liquidacion_final import liquidacion_final as _liquidacion_final


def _init_services():
    """Initialize services lazily on first tool call, not at import time."""
    global _services
    if _services is not None:
        return _services
    ensure_data_ready()
    _services = {
        "store": LegislationStore(),
        "retriever": HybridRetriever(),
        "juris": JurisprudenciaSearch(),
        "mods": ModificacionesService(),
    }
    return _services


_services = None

mcp = FastMCP(
    "ley-ar",
    instructions="Infraestructura de legislacion laboral argentina para agentes de IA",
)


@mcp.tool()
def norma_vigente(ley: str, articulo: str) -> dict:
    """Recupera el texto exacto de un articulo de legislacion laboral argentina.

    Args:
        ley: Nombre o numero de la ley
        articulo: Numero del articulo
    """
    s = _init_services()
    return _norma_vigente(s["store"], ley, articulo, mod_service=s["mods"])


@mcp.tool()
def buscar_articulos(situacion: str = None, condiciones: list = None) -> dict:
    """Devuelve los articulos de legislacion laboral aplicables a una situacion concreta.

    Determinista: cada situacion tiene un conjunto exacto de articulos definido por
    expertos legales. Los articulos incluyen su rol especifico en el caso.

    Sin parametros devuelve el catalogo de situaciones disponibles.

    Situaciones principales:
    - despido_sin_causa, despido_con_causa, despido_indirecto
    - despido_embarazo, despido_matrimonio, despido_discriminatorio
    - despido_delegado_gremial, despido_fuerza_mayor, despido_periodo_prueba
    - despido_muerte_trabajador, despido_muerte_empleador
    - renuncia, abandono_trabajo, jubilacion
    - empleo_no_registrado, accidente_trabajo, enfermedad_profesional
    - enfermedad_inculpable, diferencias_salariales, jornada_laboral
    - vacaciones, licencias, tutela_sindical, ius_variandi
    - tercerizacion, transferencia_establecimiento
    - suspension_disciplinaria, suspension_falta_trabajo
    - contrato_plazo_fijo, prescripcion, certificados_art80
    - acoso_laboral, trabajo_menores

    Se pueden combinar situaciones separandolas con coma:
    "despido_sin_causa,despido_embarazo"

    Condiciones tipicas (activan articulos adicionales):
    - no_registrado, fecha_ingreso_falsa, remuneracion_inferior
    - falta_pago_post_intimacion, causa_no_acreditada
    - sin_exclusion_previa, embarazo_durante_prueba
    - responsabilidad_civil_empleador, despido_post_accidente
    - horas_extras, renuncia_coaccionada

    Args:
        situacion: ID de la situacion laboral (o varias separadas por coma). Sin valor lista el catalogo.
        condiciones: Lista de condiciones del caso que activan articulos adicionales
    """
    s = _init_services()
    return _buscar_articulos(s["store"], situacion, condiciones, mod_service=s["mods"])


@mcp.tool()
def jurisprudencia(caso: str = None, caratula: str = None, jurisdiccion: str = None, max_resultados: int = 3) -> dict:
    """Busca jurisprudencia laboral relevante.

    Dos modos de busqueda:
    - Por caso (lenguaje natural): usa descriptores tematicos. Funciona mejor
      con descripciones conceptuales del caso, no con citas legales.
    - Por caratula (nombre del fallo): busca por texto en el nombre del caso.
      Util para fallos emblematicos (ej: "Vizzoti", "Aquino").

    Debe informarse al menos uno: caso o caratula.

    Args:
        caso: Descripcion del caso en lenguaje natural
        caratula: Texto a buscar en el nombre del fallo
        jurisdiccion: Filtro opcional por provincia
        max_resultados: Cantidad maxima de fallos a devolver. Default: 3
    """
    s = _init_services()
    return _jurisprudencia(s["retriever"], s["juris"], caso, caratula, jurisdiccion, max_resultados)


@mcp.tool()
def calcular_indemnizacion(
    fecha_ingreso: str,
    fecha_egreso: str,
    mejor_remuneracion: float,
    causa: str = "sin_causa",
    registrado: bool = True,
    preaviso_otorgado: bool = False,
    fecha_intimacion: str = None,
    remuneracion_registrada: float = None,
    fecha_registro_falsa: str = None,
    cct: str = None,
    fecha_calculo: str = None,
) -> dict:
    """Calcula rubros indemnizatorios de un despido laboral argentino.

    Deterministico. Cada monto es trazable a un articulo y una formula.
    Los rubros se clasifican en: inmediatos, requiere_intimacion y apercibimiento
    segun su exigibilidad procesal.

    Args:
        fecha_ingreso: Fecha de inicio de la relacion laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de despido (YYYY-MM-DD)
        mejor_remuneracion: Mejor remuneracion mensual normal y habitual (bruta)
        causa: Tipo de despido: "sin_causa", "con_causa", "indirecto"
        registrado: Si la relacion laboral estaba registrada
        preaviso_otorgado: Si el empleador otorgo preaviso
        fecha_intimacion: Fecha del telegrama intimando registro (YYYY-MM-DD). Omitir si no se envio.
        remuneracion_registrada: Remuneracion en recibos si habia registro parcial. Omitir si no aplica.
        fecha_registro_falsa: Fecha de ingreso registrada si era distinta a la real (YYYY-MM-DD). Omitir si no aplica.
    """
    s = _init_services()
    return _calcular_indemnizacion(
        fecha_ingreso, fecha_egreso, mejor_remuneracion, causa, registrado, preaviso_otorgado,
        fecha_intimacion, remuneracion_registrada, fecha_registro_falsa,
        mod_service=s["mods"],
        fecha_calculo=fecha_calculo,
        cct=cct,
    )


@mcp.tool()
def verificar_prescripcion(
    tipo_reclamo: str,
    fecha_hecho: str,
    fecha_consulta: str = None,
) -> dict:
    """Verifica si una accion laboral esta prescripta segun la legislacion argentina.

    Args:
        tipo_reclamo: Tipo de accion. Valores: "despido", "diferencias_salariales", "accidente", "multas_registro", "enfermedad_profesional", "acoso_laboral"
        fecha_hecho: Fecha del hecho que origina el reclamo (YYYY-MM-DD)
        fecha_consulta: Fecha de consulta (YYYY-MM-DD). Default: hoy
    """
    return _verificar_prescripcion(tipo_reclamo, fecha_hecho, fecha_consulta)


@mcp.tool()
def consultar_plazos_procesales(tipo_plazo: str = None) -> dict:
    """Consulta plazos procesales laborales: intimaciones, terminos judiciales, caducidades.

    No son plazos de prescripcion sino plazos de ejercicio dentro de un caso.
    Sin parametros lista todos los plazos disponibles.

    Args:
        tipo_plazo: Tipo de plazo. Valores: "intimacion_registro", "certificados_art80",
            "pago_indemnizacion", "seclo_audiencia", "contestacion_demanda",
            "apelacion", "copia_telegrama_afip". Si se omite, lista todos.
    """
    return _consultar_plazos_procesales(tipo_plazo)


@mcp.tool()
def consultar_cct(cct_id: str = None) -> dict:
    """Consulta convenios colectivos de trabajo y sus topes indemnizatorios (art. 245 LCT).

    Sin parametros lista todos los CCTs disponibles con sus topes.
    Con cct_id devuelve el detalle de un convenio especifico.

    Args:
        cct_id: Numero del CCT (ej: "130/75" para Comercio). Si se omite, lista todos.
    """
    return _consultar_cct(cct_id)


@mcp.tool()
def analizar_caso(
    caso: str,
    jurisdiccion: str = None,
    monto_inmediatos: float = None,
    monto_intereses: float = None,
    honorarios_pct: float = 20.0,
) -> dict:
    """Estadisticas de jurisprudencia relevante a un caso.

    Devuelve conteo de fallos clasificados como favorables/desfavorables,
    desglose por jurisdiccion, tendencia temporal, y alertas factuales.
    La clasificacion es automatica (patrones de texto) — ver campo metodologia.

    Args:
        caso: Descripcion del caso en lenguaje natural
        jurisdiccion: Filtro opcional por provincia
        monto_inmediatos: Total de rubros inmediatos para estimar costos de litigio
        monto_intereses: Intereses calculados
        honorarios_pct: Porcentaje de honorarios (default 20%)
    """
    s = _init_services()
    return _analizar_caso(
        s["retriever"], s["juris"], caso, jurisdiccion,
        monto_inmediatos=monto_inmediatos,
        monto_intereses=monto_intereses,
        honorarios_pct=honorarios_pct,
    )


@mcp.tool()
def generar_documento(
    tipo: str,
    datos_trabajador: dict,
    datos_empleador: dict,
    datos_caso: dict,
    calculo: dict = None,
) -> dict:
    """Genera un documento legal completo listo para revision.

    Tipos: "telegrama_registro", "carta_documento", "liquidacion".

    Args:
        tipo: Tipo de documento
        datos_trabajador: { nombre, cuil, domicilio }
        datos_empleador: { razon_social, cuit, domicilio }
        datos_caso: { fecha_ingreso, fecha_egreso, remuneracion, causa, lugar }
        calculo: Output de calcular_indemnizacion
    """
    return _generar_documento(tipo, datos_trabajador, datos_empleador, datos_caso, calculo)


@mcp.tool()
def calcular_intereses(
    monto_base: float,
    fecha_desde: str,
    fecha_hasta: str = None,
) -> dict:
    """Calcula intereses a tasa activa del Banco Nacion Argentina.

    Interes simple mes a mes con la tasa vigente de cada periodo.

    Args:
        monto_base: Capital sobre el que se calculan intereses
        fecha_desde: Fecha de inicio del devengamiento (YYYY-MM-DD)
        fecha_hasta: Fecha de calculo (YYYY-MM-DD). Default: hoy
    """
    return _calcular_intereses(monto_base, fecha_desde, fecha_hasta)


@mcp.tool()
def obtener_fallo(numero_sumario: str) -> dict:
    """Recupera el texto completo de un fallo por su numero de sumario.

    Args:
        numero_sumario: Identificador del fallo
    """
    s = _init_services()
    return _obtener_fallo(s["juris"], numero_sumario)


@mcp.tool()
def liquidacion_final(
    fecha_ingreso: str,
    fecha_egreso: str,
    remuneracion: float,
    motivo: str = "renuncia",
    dias_vacaciones_gozadas: int = 0,
) -> dict:
    """Calcula la liquidacion final sin rubros indemnizatorios.

    Incluye: dias trabajados, SAC proporcional, vacaciones proporcionales.

    Args:
        fecha_ingreso: Fecha de inicio de la relacion laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de finalizacion (YYYY-MM-DD)
        remuneracion: Ultima remuneracion mensual bruta
        motivo: "renuncia", "jubilacion", "mutuo_acuerdo", "fin_contrato_plazo_fijo", "fallecimiento". Default: "renuncia"
        dias_vacaciones_gozadas: Dias de vacaciones ya gozadas en el anio. Default: 0
    """
    return _liquidacion_final(fecha_ingreso, fecha_egreso, remuneracion, motivo, dias_vacaciones_gozadas)

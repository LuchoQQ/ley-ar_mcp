from mcp.server.fastmcp import FastMCP

from ley_ar.data_manager import ensure_data_ready
from ley_ar.services.legislation_store import LegislationStore
from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch
from ley_ar.tools.norma_vigente import norma_vigente as _norma_vigente
from ley_ar.tools.calcular_indem import calcular_indemnizacion as _calcular_indemnizacion
from ley_ar.tools.verificar_prescrip import verificar_prescripcion as _verificar_prescripcion
from ley_ar.tools.buscar_articulos import buscar_articulos as _buscar_articulos
from ley_ar.tools.jurisprudencia import jurisprudencia as _jurisprudencia
from ley_ar.tools.analizar_caso import analizar_caso as _analizar_caso
from ley_ar.tools.generar_documento import generar_documento as _generar_documento
from ley_ar.services.modificaciones_service import ModificacionesService

ensure_data_ready()

legislation_store = LegislationStore()
hybrid_retriever = HybridRetriever()
juris_search = JurisprudenciaSearch()
mod_service = ModificacionesService()

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
    return _norma_vigente(legislation_store, ley, articulo, mod_service=mod_service)


@mcp.tool()
def buscar_articulos(tema: str, ley: str = None, max_resultados: int = 5) -> dict:
    """Busqueda semantica de articulos de legislacion laboral por tema.

    Usa descriptores tematicos y embeddings. Funciona con descripciones
    conceptuales del caso, no con citas legales especificas.

    Args:
        tema: Descripcion del tema en lenguaje natural
        ley: Filtro opcional por ley
        max_resultados: Cantidad maxima de articulos a devolver. Default: 5
    """
    return _buscar_articulos(hybrid_retriever, legislation_store, tema, ley, max_resultados, mod_service=mod_service)


@mcp.tool()
def jurisprudencia(caso: str, jurisdiccion: str = None, max_resultados: int = 3) -> dict:
    """Busca jurisprudencia laboral relevante a un caso.

    Usa descriptores tematicos. Funciona mejor con descripciones del caso
    que con citas legales especificas.

    Args:
        caso: Descripcion del caso en lenguaje natural
        jurisdiccion: Filtro opcional por provincia
        max_resultados: Cantidad maxima de fallos a devolver. Default: 3
    """
    return _jurisprudencia(hybrid_retriever, juris_search, caso, jurisdiccion, max_resultados)


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
    return _calcular_indemnizacion(
        fecha_ingreso, fecha_egreso, mejor_remuneracion, causa, registrado, preaviso_otorgado,
        fecha_intimacion, remuneracion_registrada, fecha_registro_falsa,
        mod_service=mod_service,
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
        tipo_reclamo: Tipo de accion. Valores: "despido", "diferencias_salariales", "accidente", "multas_registro"
        fecha_hecho: Fecha del hecho que origina el reclamo (YYYY-MM-DD)
        fecha_consulta: Fecha de consulta (YYYY-MM-DD). Default: hoy
    """
    return _verificar_prescripcion(tipo_reclamo, fecha_hecho, fecha_consulta)


@mcp.tool()
def analizar_caso(
    caso: str,
    jurisdiccion: str = None,
    monto_inmediatos: float = None,
    monto_intereses: float = None,
    honorarios_pct: float = 20.0,
) -> dict:
    """Analiza estadisticamente la jurisprudencia relevante a un caso.

    Devuelve tasa de exito, estadisticas por jurisdiccion, tendencia temporal,
    alertas sobre doctrina contradictoria, y analisis costo-beneficio.

    Args:
        caso: Descripcion del caso en lenguaje natural
        jurisdiccion: Filtro opcional por provincia
        monto_inmediatos: Total de rubros inmediatos para analisis costo-beneficio
        monto_intereses: Intereses calculados
        honorarios_pct: Porcentaje de honorarios (default 20%)
    """
    return _analizar_caso(
        hybrid_retriever, juris_search, caso, jurisdiccion,
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

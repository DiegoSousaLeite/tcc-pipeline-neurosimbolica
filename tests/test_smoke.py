"""Teste de fumaça: garante que a esteira de testes está de pé e que os
módulos principais importam sem efeito colateral de rede ou de API."""


def test_pytest_configurado():
    assert True


def test_imports_principais():
    import run_pipeline
    from src import fase1_semgrep, fase2_middleware, fase5_auditoria, hidratacao

    assert hasattr(run_pipeline, "construir_casos_fp")
    assert hasattr(fase1_semgrep, "executar_semgrep")
    assert hasattr(fase2_middleware, "extrair_e_hidratar_contexto")
    assert hasattr(fase5_auditoria, "registrar_resultado")
    assert hasattr(hidratacao, "extrai_funcao")

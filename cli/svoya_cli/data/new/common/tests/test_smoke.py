def test_import():
    import {{ project.package }}

    assert {{ project.package }}.__version__

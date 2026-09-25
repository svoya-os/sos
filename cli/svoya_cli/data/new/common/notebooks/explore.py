import marimo

app = marimo.App()


@app.cell
def _():
    import {{ project.package }}

    return ({{ project.package }},)


if __name__ == "__main__":
    app.run()

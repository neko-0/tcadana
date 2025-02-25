import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules=[
        'parser',
        'tools.triangles',
        'tools.database',
    ],
    submod_attrs={
        'version': ['__version__'],
        'parser': ['open_tdr'],
    },
)

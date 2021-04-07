import fig_runner
import main
from fig_utils import FakeFDL


if __name__ == "__main__":
    fig_runner._initializer_runner()
    FakeFDL(fig_runner._handler, {}, {}).run()

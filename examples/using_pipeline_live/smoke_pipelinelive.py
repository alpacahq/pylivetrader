import examples.using_pipeline_live.pipeline_live_example as algo

from pylivetrader.testing.smoke import harness


def test_algo():
    pipe = harness.DefaultPipelineHooker()

    harness.run_smoke(algo,
                      pipeline_hook=pipe,
                      )


if __name__ == '__main__':
    import sys
    from logbook import StreamHandler
    StreamHandler(sys.stdout).push_application()

    test_algo()

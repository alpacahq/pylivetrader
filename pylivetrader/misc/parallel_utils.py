import concurrent.futures
import os


def _get_default_workers():
    workers = os.environ.get('PYLT_NUM_WORKERS')
    return int(workers) if workers else 10


def parallelize(mapfunc, workers=None):
    '''
    Parallelize the mapfunc with multithreading. mapfunc calls will be
    partitioned by the provided list of arguments. Each item in the list
    will represent one call's arguments. They can be tuples if the function
    takes multiple arguments, but one-tupling is not necessary.

    If workers argument is not provided, workers will be pulled from an
    environment variable PYLT_NUM_WORKERS. If the environment variable is not
    found, it will default to 10 workers.

    Return: func(args_list: list[arg]) => dict[arg -> result]
    '''
    workers = workers if workers else _get_default_workers()

    def wrapper(args_list):
        result = {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers) as executor:
            tasks = {}
            for args in args_list:
                if isinstance(args, tuple):
                    task = executor.submit(mapfunc, *args)
                else:
                    task = executor.submit(mapfunc, args)
                tasks[task] = args

            for task in concurrent.futures.as_completed(tasks):
                args = tasks[task]
                task_result = task.result()
                result[args] = task_result
        return result

    return wrapper

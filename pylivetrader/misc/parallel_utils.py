import concurrent.futures


def parallelize(mapfunc, workers=10):
    '''
    Parallelize the mapfunc with multithreading. mapfunc calls will be
    partitioned by the provided list of arguments. Each item in the list
    will represent one call's arguments. They can be tuples if the function
    takes multiple arguments, but one-tupling is not necessary.

    Return: func(args_list: list[arg]) => dict[arg -> result]
    '''

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

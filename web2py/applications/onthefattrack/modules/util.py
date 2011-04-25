def contains_all(list, list_to_check):
    return reduce(lambda x, y: x and y in list, list_to_check)

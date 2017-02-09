# coding:utf-8

import math
import config
import peewee
from playhouse.db_url import connect
from playhouse.shortcuts import _clone_set

db = connect(config.DATABASE_URI)


class BaseModel(peewee.Model):
    class Meta:
        database = db

    def model_to_dict(self, recurse=True, backrefs=False, only=None,
                      exclude=None, seen=None, extra_attrs=None,
                      fields_from_query=None, max_depth=None):
        model = self
        max_depth = -1 if max_depth is None else max_depth
        if max_depth == 0:
            recurse = False

        only = _clone_set(only)
        extra_attrs = _clone_set(extra_attrs)

        if fields_from_query is not None:
            for item in fields_from_query._select:
                if isinstance(item, Field):
                    only.add(item)
                elif isinstance(item, Node) and item._alias:
                    extra_attrs.add(item._alias)

        data = {}
        exclude = _clone_set(exclude)
        seen = _clone_set(seen)
        exclude |= seen
        model_class = type(model)

        for field in model._meta.declared_fields:
            if field in exclude or (only and (field not in only)):
                continue

            field_data = model._data.get(field.name)
            if isinstance(field, peewee.ForeignKeyField) and recurse:
                if field_data:
                    seen.add(field)
                    rel_obj = getattr(model, field.name)
                    field_data = rel_obj.model_to_dict(recurse=recurse, backrefs=backrefs, only=only, exclude=exclude,
                                                       seen=seen, max_depth=max_depth - 1)
                else:
                    field_data = {}

            data[field.name] = field_data

        if extra_attrs:
            for attr_name in extra_attrs:
                attr = getattr(model, attr_name)
                if callable(attr):
                    data[attr_name] = attr()
                else:
                    data[attr_name] = attr

        if backrefs and recurse:
            for related_name, foreign_key in model._meta.reverse_rel.items():
                descriptor = getattr(model_class, related_name)
                if descriptor in exclude or foreign_key in exclude:
                    continue
                if only and (descriptor not in only) and (foreign_key not in only):
                    continue

                accum = []
                exclude.add(foreign_key)
                related_query = getattr(
                    model,
                    related_name + '_prefetch',
                    getattr(model, related_name))

                for rel_obj in related_query:
                    accum.append(rel_obj.model_to_dict(recurse=recurse, backrefs=backrefs, only=only, exclude=exclude,
                                                       max_depth=max_depth - 1))

                data[related_name] = accum

        return data

    @classmethod
    def get_by_pk(cls, value):
        try:
            return cls.get(cls._meta.primary_key == value)
        except cls.DoesNotExist:
            return

    @classmethod
    def exists_by_pk(cls, value):
        return cls.select().where(cls._meta.primary_key == value).exists()


def pagination(count_all, query, page_size, cur_page=1, nearby=2):
    """
    :param count_all: count of all items
    :param query: a peewee query object
    :param page_size: size of one page
    :param cur_page: current page number, accept string digit
    :return: num of pages, an iterator
    """
    if type(cur_page) == str:
        cur_page = int(cur_page) if cur_page.isdigit() else 1
    elif type(cur_page) == int:
        if cur_page <= 0:
            cur_page = 1
    else:
        cur_page = 1

    page_count = int(math.ceil(count_all / page_size))
    items_length = nearby * 2 + 1

    # if first page in page items, first_page is None,
    # it means the "go to first page" button should not be available.
    first_page = None
    last_page = None

    prev_page = cur_page - 1 if cur_page != 1 else None
    next_page = cur_page + 1 if cur_page != page_count else None

    if page_count <= items_length:
        items = range(1, page_count+1)
    elif cur_page <= nearby:
        # start of items
        items = range(1, items_length+1)
        last_page = True
    elif cur_page >= page_count - nearby:
        # end of items
        items = range(page_count - items_length+1, page_count+1)
        first_page = True
    else:
        items = range(cur_page - nearby, cur_page + nearby + 1)
        first_page, last_page = True, True

    if first_page:
        first_page = 1
    if last_page:
        last_page = page_count

    return {
        'cur_page': cur_page,
        'prev_page': prev_page,
        'next_page': next_page,

        'first_page': first_page,
        'last_page': last_page,

        'page_numbers': items,
        'page_count': page_count,

        'items': query.paginate(cur_page, page_size),
    }

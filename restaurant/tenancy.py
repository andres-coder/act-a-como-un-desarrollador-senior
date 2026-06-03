def scoped_queryset(queryset, user, lookup='restaurant'):
    if user.is_superuser or not getattr(user, 'restaurant_id', None):
        return queryset
    return queryset.filter(**{lookup: user.restaurant})

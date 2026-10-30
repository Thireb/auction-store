"""Small list / add / edit pages for simple models (categories, brands, lots, cities ...).

Permissions follow the Django model permissions: view for the list, add for "New",
change to save. Only the owner deletes, and only where `owner_delete` is set.
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from ..access import portal_view
from ..forms import StyledFormMixin
from ..history import object_history

PAGE_SIZE = 50


class Crud:
    model = None
    name = ""  # URL names: <name>_list, <name>_add, <name>_edit, <name>_delete
    fields = []
    form_class = None
    columns = []  # (label, attribute name or function)
    search_fields = []
    filters = []  # model field names: booleans, choices or foreign keys
    owner_delete = False
    help_text = ""

    # Hooks ---------------------------------------------------------------------------

    def get_queryset(self, request):
        return self.model._default_manager.all()

    def get_fields(self, request, obj=None):
        return self.fields

    def get_form_class(self, request, obj=None):
        base = self.form_class or type("CrudForm", (StyledFormMixin, forms.ModelForm), {})
        return modelform_factory(self.model, form=base, fields=self.get_fields(request, obj))

    def edit_context(self, request, obj):
        return {}

    def save(self, request, form):
        return form.save()

    # Helpers -------------------------------------------------------------------------

    @property
    def opts(self):
        return self.model._meta

    def perm(self, action):
        return f"{self.opts.app_label}.{action}_{self.opts.model_name}"

    def url(self, kind, *args):
        return reverse(f"portal:{self.name}_{kind}", args=args)

    def cell(self, obj, column):
        attr = column[1]
        if callable(attr):
            return attr(obj)
        display = getattr(obj, f"get_{attr}_display", None)
        value = display() if display else getattr(obj, attr)
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "" if value is None else value

    def filter_choices(self, field_name):
        field = self.opts.get_field(field_name)
        if field.get_internal_type() == "BooleanField":
            return [("1", "Yes"), ("0", "No")]
        if field.choices:
            return [(str(k), v) for k, v in field.choices]
        related = field.related_model._default_manager.all()[:200]
        return [(str(o.pk), str(o)) for o in related]

    def apply_filters(self, request, queryset):
        active = {}
        for name in self.filters:
            value = request.GET.get(name, "")
            if not value:
                continue
            active[name] = value
            field = self.opts.get_field(name)
            if field.get_internal_type() == "BooleanField":
                queryset = queryset.filter(**{name: value == "1"})
            else:
                queryset = queryset.filter(**{name: value})
        q = request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            queryset = queryset.filter(cond).distinct()
        return queryset, active, q

    # Views ---------------------------------------------------------------------------

    def list_view(self, request):
        queryset, active, q = self.apply_filters(request, self.get_queryset(request))
        if not queryset.ordered:
            queryset = queryset.order_by(*(self.opts.ordering or ["-pk"]))
        page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
        query = request.GET.copy()
        query.pop("page", None)
        rows = [
            (self.url("edit", obj.pk), [self.cell(obj, c) for c in self.columns])
            for obj in page.object_list
        ]
        context = {
            "crud": self,
            "title": self.opts.verbose_name_plural.capitalize(),
            "headers": [c[0] for c in self.columns],
            "rows": rows,
            "page_obj": page,
            "query_string": query.urlencode(),
            "filters": [
                (n, self.opts.get_field(n).verbose_name.capitalize(), self.filter_choices(n))
                for n in self.filters
            ],
            "active": active,
            "q": q,
            "can_add": request.user.has_perm(self.perm("add")),
        }
        return render(request, "portal/crud_list.html", context)

    def edit_view(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(request), pk=pk) if pk else None
        if obj is None and not request.user.has_perm(self.perm("add")):
            raise PermissionDenied
        can_save = request.user.has_perm(self.perm("change" if obj else "add"))
        form_class = self.get_form_class(request, obj)
        data = request.POST if request.method == "POST" and can_save else None
        form = form_class(data, request.FILES or None, instance=obj)
        if not can_save:
            for field in form.fields.values():
                field.disabled = True
        if data is not None and form.is_valid():
            saved = self.save(request, form)
            messages.success(request, f"Saved {self.opts.verbose_name} “{saved}”.")
            if "add_another" in request.POST:
                return redirect(self.url("add"))
            return redirect(self.url("edit", saved.pk))
        context = {
            "crud": self,
            "title": str(obj) if obj else f"New {self.opts.verbose_name}",
            "obj": obj,
            "form": form,
            "can_save": can_save,
            "can_delete": obj is not None and self.owner_delete and request.user.is_superuser,
            "history": object_history(obj) if obj else [],
            **(self.edit_context(request, obj) if obj else {}),
        }
        return render(request, "portal/crud_form.html", context)

    def delete_view(self, request, pk):
        if not (self.owner_delete and request.user.is_superuser) or request.method != "POST":
            raise PermissionDenied
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(request, f"“{obj}” is in use. Hide it instead.")
            return redirect(self.url("edit", pk))
        messages.success(request, f"Deleted “{obj}”.")
        return redirect(self.url("list"))

    def urls(self, prefix):
        view, add, change = self.perm("view"), self.perm("add"), self.perm("view")
        return [
            path(f"{prefix}/", portal_view(view)(self.list_view), name=f"{self.name}_list"),
            path(f"{prefix}/new/", portal_view(add)(self.edit_view), name=f"{self.name}_add"),
            path(
                f"{prefix}/<int:pk>/",
                portal_view(change)(self.edit_view),
                name=f"{self.name}_edit",
            ),
            path(
                f"{prefix}/<int:pk>/delete/",
                portal_view()(self.delete_view),
                name=f"{self.name}_delete",
            ),
        ]

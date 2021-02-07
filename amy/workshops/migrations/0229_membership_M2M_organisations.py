# Generated by Django 2.2.17 on 2021-02-07 11:54

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_ROLES = (("default", "Default"),)


def create_default_member_roles(apps, schema_editor):
    """Create a default MemberRole. It's required in M2M relationship between
    Memberships and Organisations."""
    MemberRole = apps.get_model("workshops", "MemberRole")
    objects = [
        MemberRole(name=name, verbose_name=verbose_name)
        for name, verbose_name in DEFAULT_ROLES
    ]
    MemberRole.objects.bulk_create(objects)


def remove_default_member_roles(apps, schema_editor):
    """Remove the default-created MemberRole."""
    MemberRole = apps.get_model("workshops", "MemberRole")
    role_names = [name for name, _ in DEFAULT_ROLES]
    MemberRole.objects.filter(name__in=role_names).delete()


def copy_organisation_to_organisations(apps, schema_editor):
    """Copy single FK organization to entry in M2M through table (Member). Use
    the default role created in previous data migration."""
    Member = apps.get_model("workshops", "Member")
    MemberRole = apps.get_model("workshops", "MemberRole")
    default_role = MemberRole.objects.get(name=DEFAULT_ROLES[0][0])
    Membership = apps.get_model("workshops", "Membership")

    for membership in Membership.objects.all():
        Member.objects.create(
            membership=membership,
            organization=membership.organization,
            role=default_role,
        )


def copy_default_organisations_to_organisation(apps, schema_editor):
    """Reverse `copy_organisation_to_organisations`."""
    Member = apps.get_model("workshops", "Member")
    MemberRole = apps.get_model("workshops", "MemberRole")
    default_role = MemberRole.objects.get(name=DEFAULT_ROLES[0][0])

    for member in Member.objects.filter(role=default_role):
        membership = member.membership
        membership.organization = member.organization
        membership.save()


class Migration(migrations.Migration):
    dependencies = [
        ("workshops", "0228_auto_20210204_0658"),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberRole",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=40)),
                (
                    "verbose_name",
                    models.CharField(max_length=100, blank=True, default=""),
                ),
            ],
        ),
        migrations.RunPython(create_default_member_roles, remove_default_member_roles),
        migrations.CreateModel(
            name="Member",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "membership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="workshops.Membership",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="workshops.Organization",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="workshops.MemberRole",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="membership",
            name="organizations",
            field=models.ManyToManyField(
                related_name="memberships",
                through="workshops.Member",
                to="workshops.Organization",
            ),
        ),
        migrations.RunPython(
            copy_organisation_to_organisations,
            copy_default_organisations_to_organisation,
        ),
        migrations.RemoveField(
            model_name="membership",
            name="organization",
        ),
    ]

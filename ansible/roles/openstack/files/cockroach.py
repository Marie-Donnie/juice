"""
   `CockroachDB`_ database specific implementations of changeset classes.

   .. _`CockroachDB`: http://www.postgresql.org/
"""
from .. import ansisql
from ..databases import postgres

import sqlalchemy
from sqlalchemy.schema import DropConstraint
from sqlalchemy.engine import reflection
from sqlalchemy.databases import postgresql

import copy
from operator import attrgetter

def compose(f, g):
    return lambda x: f(g(x))

# ------------------------------------------- CockroachDB Dialects Workaround
# CockroachDB Dialect misses BOOL type name
from cockroachdb.sqlalchemy.dialect import _type_map, CockroachDBDialect
_type_map['bool'] = _type_map['boolean']

class CockroachDDLCompiler(postgresql.PGDDLCompiler):
    # Handle: sqlalchemy.Column(sqlalchemy.ForeignKey())
    # See, https://github.com/zzzeek/sqlalchemy/blob/6448903b5287801aaefbf82b5fa108403d743e8f/lib/sqlalchemy/sql/compiler.py#L2673
    def visit_foreign_key_constraint(self, constraint):
        # Only support ON DELETE/UPDATE RESTRICT.
        if constraint.ondelete:
            constraint.ondelete = "RESTRICT"
        if constraint.onupdate:
            constraint.onupdate = "RESTRICT"

        super(CockroachDDLCompiler, self).visit_foreign_key_constraint(constraint)

    def visit_drop_index(self, drop):
        """DROP INDEX ...

        CockroachDB doesn't support the drop of table's `primary`
        index. This workaround passes the drop and doesn't delete the
        index if it's primary one.

        See, https://www.cockroachlabs.com/docs/stable/drop-index.html

        """
        index = drop.element

        if index.name == 'primary':
            return "SELECT 1"
        else:
            return super(CockroachDDLCompiler, self).visit_drop_index(drop)


CockroachDBDialect.ddl_compiler = CockroachDDLCompiler


# -------------------------------------------- Handle migration
class CockroachAlterTableVisitor(ansisql.AlterTableVisitor):
    def clean_context(self, l):
        self.buffer.seek(0)
        self.buffer.truncate()
        l();
        self.append("SELECT 1")

    def recreate_table(self, table, effects):
        """Recreates a table with some modifications.

        Make a new temporary table, applies `effects` and copy
        elements of the original table. Then drop the original table
        and rename the temporary one.

        The `effects` function takes the SQLAlchemy::Table object in
        parameter, so the `effects` function can change it before the
        table creation.

        """
        # Build the temporary table
        curr_table = table
        tmp_columns = [c.copy() for c in curr_table.columns]
        tmp_table = sqlalchemy.Table(curr_table.name + '_migrate_tmp',
                                     sqlalchemy.MetaData(bind=curr_table.metadata.bind),
                                     *tmp_columns)

        # Apply custom effects on the tmp_table and create it
        effects(tmp_table)
        tmp_table.create()

        # Fill the temporary table with the original one
        tmp_table.insert().from_select(
            [c.name for c in curr_table.columns],
            curr_table.select())

        # Remove the original table and rename the temporary one
        tname = self.preparer.format_table(curr_table)
        tmp_tname = self.preparer.format_table(tmp_table)
        self.append("DROP TABLE %s CASCADE" % tname)
        self.execute()
        self.append("ALTER TABLE %s RENAME TO %s" % (tmp_tname, tname))
        self.execute()


class CockroachColumnGenerator(postgres.PGColumnGenerator, CockroachAlterTableVisitor):
    """CockroachDB column generator implementation.

    ALTER TABLE ... ADD COLUMN
    """
    def add_foreignkey(self, fk):
        from .visitor import get_engine_visitor, run_single_visitor

        tname = fk.table.name
        cnames = map(self.preparer.format_column, fk.columns.values())
        fk.name = "%s_%s_fkey" % (tname, cnames[0])
        fk.__migrate_visit_name__ = 'migrate_foreign_key_constraint'

        engine = fk.table.metadata.bind
        visitor = get_engine_visitor(engine, 'constraintgenerator')
        run_single_visitor(engine, visitor, fk)


class CockroachColumnDropper(postgres.PGColumnDropper, CockroachAlterTableVisitor):
    """CockroachDB column dropper implementation.


    ALTER TABLE ... DROP COLUMN
    """
    def visit_column(self, column):
        """Drop a column from its table.

        :param column: the column object
        :type column: :class:`sqlalchemy.Column`
        """
        # Drop Constraint First
        from .visitor import get_engine_visitor, run_single_visitor
        engine = column.table.metadata.bind
        visitor = get_engine_visitor(engine, 'constraintdropper')

        for fk in column.foreign_keys:
            fk.__migrate_visit_name__ = 'migrate_foreign_key_constraint'
            run_single_visitor(engine, visitor, fk.constraint)

        if column.primary_key:
            pk = column.table.primary_key
            pk.__migrate_visit_name__ = 'migrate_primary_key_constraint'
            run_single_visitor(engine, visitor, pk)

        # TODO: Drop CHECK/UNIQUE?

        # Proceed
        super(CockroachColumnDropper, self).visit_column(column)


class CockroachSchemaChanger(postgres.PGSchemaChanger, CockroachAlterTableVisitor):
    """CockroachDB schema changer implementation.

    ALTER TABLE ... ALTER COLUMN ...

    See, https://www.cockroachlabs.com/docs/stable/alter-column.html
    """
    @staticmethod
    def copy_delta(delta, key):
        "Copies ColumnDelta `delta` and only keeps the key modification."
        to_remove_keys = filter(
            key.__ne__, ['name', 'type', 'primary_key', 'nullable',
                         'server_onupdate', 'server_default',
                         'autoincrement'])

        delta_ = copy.copy(delta)
        delta_.diffs = delta.diffs.copy()

        for k in to_remove_keys:
            delta_.diffs.pop(k, False)

        return delta_

    def visit_column(self, delta):
        """Rename/change a column."""
        # ALTER COLUMN is implemented as several ALTER statements
        table = self._to_table(delta.table)
        column = delta.result_column
        alter_type = delta.keys()

        # ALTER COLUMN ... SET NOT NULL not implemented by
        # CockroachDB. Only do nullable if it's a SET NULL.
        set_null = delta.get('nullable', False)
        if set_null:
            super(CockroachSchemaChanger, self).visit_column(
                CockroachSchemaChanger.copy_delta(delta, 'nullable'))

        # ALTER COLUMN ... TYPE <type> is not implemented by
        # CockroachDB. Go through a temp table to implement it.
        the_type = delta.get('type', False)
        if the_type:
            self._visit_column_type(table, column, the_type)

        # ALTER COLUMN ... SET/DROP DEFAULT is well implemented in
        # CockroachDB. Fallback to ANSISQL implementation.
        default = delta.get('server_default', False)
        if default:
            super(CockroachSchemaChanger, self).visit_column(
                CockroachSchemaChanger.copy_delta(delta, 'server_default'))

        # ALTER COLUMN ... RENAME COLUMN ... TO ... is well
        # implemented in CockroachDB. Fallback to ANSISQL
        # implementation.
        rename = delta.get('name', False)
        if rename:
            super(CockroachSchemaChanger, self).visit_column(
                CockroachSchemaChanger.copy_delta(delta, 'name'))

    def _visit_column_type(self, table, column, the_type):
        """ALTER COLUMN ... TYPE <type>

        Not implemented by CockroachDB. To implement this migration,
        first make a new temporary table with the new type and copy
        elements of the original table. Then drop the original table
        and rename the temporary one.

        """
        def set_column_type(table):
            for col in filter(compose(column.name.__eq__, attrgetter('name')),
                              table.columns):
                col.type = the_type

        # Recreates the table by changing the type of the column
        self.recreate_table(table, set_column_type)


class CockroachConstraintGenerator(postgres.PGConstraintGenerator, CockroachAlterTableVisitor):
    """CockroachDB constraint generator (`create`) implementation.

    The ADD CONSTRAINT statement add Check, Foreign Key and Unique
    constraint to columns.

    See, https://www.cockroachlabs.com/docs/stable/add-constraint.html

    """
    def visit_migrate_primary_key_constraint(self, constraint):
        """Add the Primary Key constraint.

        CockroachDB does not support the add of a Primary Key
        constraint. To implement this migration, first make a new
        temporary table with the new primary key and copy elements of
        the original table. Then drop the original table and rename
        the temporary one.

        """
        pk_names = map(attrgetter('name'), constraint.columns.values())
        def set_primary_keys(table):
            for col in table.columns:
                if col.name in pk_names:
                    col.primary_key = True
                else:
                    col.primary_key = False

        # Recreates the table by changing the type of the column
        self.recreate_table(constraint.table, set_primary_keys)


    def visit_migrate_foreign_key_constraint(self, constraint):
        """Add the Foreign Key Constraint.

        Note:
        - CockroachDB only support ON DELETE/UPDATE RESTRICT
        - Before you can add the Foreign Key constraint to columns,
          the columns must already be indexed. If they are not already
          indexed, use CREATE INDEX to index them and only then use
          the ADD CONSTRAINT statement to add the Foreign Key
          constraint to the columns.

        See,
        https://www.cockroachlabs.com/docs/stable/add-constraint.html#add-the-foreign-key-constraint
        https://github.com/cockroachdb/cockroach/blob/4d587b1f19582c19b4c44c4fcc2b58efa38a57ed/pkg/sql/parser/sql.y#L2974
        """
        # Only support ON DELETE/UPDATE RESTRICT.
        if constraint.ondelete:
            constraint.ondelete = "RESTRICT"
        if constraint.onupdate:
            constraint.onupdate = "RESTRICT"

        # -- Make index
        # Table that will receive a FK
        tname = self.preparer.format_table(constraint.table)
        # Columns in the FK (have to be indexed)
        cnames = map(self.preparer.format_column, constraint.columns.values())
        # Index
        self.append("CREATE INDEX cockroach_fk_%s ON %s (%s)" %
                    ('_'.join(cnames), tname, ', '.join(cnames)))
        self.execute()

        # Proceed
        super(CockroachConstraintGenerator, self).visit_migrate_foreign_key_constraint(constraint)

        # Validate the FK constraint
        # See, https://github.com/cockroachdb/docs/issues/990
        self.append("ALTER TABLE %s VALIDATE CONSTRAINT %s" %
                    (tname, constraint.name))
        self.execute()

class CockroachConstraintDropper(postgres.PGConstraintDropper, CockroachAlterTableVisitor):
    """CockroachDB constraint dropper (`drop`) implementation.

    The DROP CONSTRAINT statement removes Check and Foreign Key
    constraints from columns.

    See,
    https://www.cockroachlabs.com/docs/stable/drop-constraint.html

    """
    @staticmethod
    def _to_index(table):
        def closure(index_name):
            idx = sqlalchemy.Index(index_name)
            idx.table = table
            return idx

        return closure

    def visit_migrate_foreign_key_constraint(self, constraint):
        # First, drop fk
        constraint.cascade = False
        super(CockroachConstraintDropper, self).visit_migrate_foreign_key_constraint(constraint)

        # Then, drop index created in
        # CockroachConstraintGenerator::visit_migrate_foreign_key_constraint
        #
        # Table that has received a FK
        tname = self.preparer.format_table(constraint.table)
        # Columns in the FK (have been indexed)
        cnames = map(self.preparer.format_column, constraint.columns.values())
        # Drop Index
        self.append("DROP INDEX %s@cockroach_fk_%s" %
                    (tname, '_'.join(cnames)))
        self.execute()

    def visit_migrate_primary_key_constraint(self, constraint):
        """Do not drop constraint"""
        pass

    def visit_migrate_unique_constraint(self, constraint):
        """Drop INDEX if the unique constraint is one"""
        # Get indexes on that columns
        insp = reflection.Inspector.from_engine(constraint.table.metadata.bind)
        indexes = set([i['name']
                       for i in insp.get_indexes(constraint.table)
                       for c in i['column_names']
                       if i['unique'] and c in constraint.columns])
        indexes = map(CockroachConstraintDropper._to_index(constraint.table), indexes)

        # Drop index if constraint is one or proceed
        if indexes:
           for i in indexes:
               self.append("DROP INDEX %s CASCADE" % self._prepared_index_name(i))
               self.execute()
        else:
            super(CockroachConstraintDropper, self).visit_migrate_unique_constraint(constraint)

class CockroachDialect(postgres.PGDialect):
    columngenerator = CockroachColumnGenerator
    columndropper = CockroachColumnDropper
    schemachanger = CockroachSchemaChanger
    constraintgenerator = CockroachConstraintGenerator
    constraintdropper = CockroachConstraintDropper

class SQLQueryBuilder:
    @staticmethod
    def select(table, columns=None, where=None):
        if columns is None:
            columns = ["*"]
        if where is None:
            where = []
        query = []
        if len(columns) == 1 and columns[0] == "*":
            query.append("SELECT *")
        else:
            query.append("SELECT " + ", ".join(columns))
        query.append(f" FROM {table}")
        if where:
            query.append(" WHERE " + " AND ".join([f"{key}='{value}'" for key, value in where]))
        return "".join(query)

    @staticmethod
    def insert(table, data):
        query = []
        query.append(f"INSERT INTO {table} (")
        query.append(", ".join([item[0] for item in data]))
        query.append(") VALUES (")
        query.append(", ".join([f"'{item[1]}'" for item in data]))
        query.append(")")
        return "".join(query)

    @staticmethod
    def delete_(table, where=None):
        if where is None:
            where = []
        query = []
        query.append(f"DELETE FROM {table}")
        if where:
            query.append(" WHERE " + " AND ".join([f"{item[0]}='{item[1]}'" for item in where]))
        return "".join(query)

    @staticmethod
    def update(table, data, where=None):
        if where is None:
            where = []
        query = []
        query.append(f"UPDATE {table} SET ")
        query.append(", ".join([f"{item[0]}='{item[1]}'" for item in data]))
        if where:
            query.append(" WHERE " + " AND ".join([f"{item[0]}='{item[1]}'" for item in where]))
        return "".join(query)

class SQLGenerator:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, fields=None, condition=""):
        if fields is None:
            fields = []
        fields_str = "*"
        if fields:
            fields_str = fields[0]
            for i in range(1, len(fields)):
                fields_str += ", " + fields[i]

        sql = f"SELECT {fields_str} FROM {self.table_name}"
        if condition:
            sql += f" WHERE {condition}"
        return sql + ";"

    def insert(self, data):
        fields_stream = []
        values_stream = []
        for i, (key, value) in enumerate(data.items()):
            if i != 0:
                fields_stream.append(", ")
                values_stream.append(", ")
            fields_stream.append(key)
            values_stream.append(f"'{value}'")

        fields_str = "".join(fields_stream)
        values_str = "".join(values_stream)
        sql = f"INSERT INTO {self.table_name} ({fields_str}) VALUES ({values_str})"
        return sql + ";"

    def update(self, data, condition):
        set_clause_stream = []
        for i, (key, value) in enumerate(data.items()):
            if i != 0:
                set_clause_stream.append(", ")
            set_clause_stream.append(f"{key} = '{value}'")

        set_clause_str = "".join(set_clause_stream)
        sql = f"UPDATE {self.table_name} SET {set_clause_str}"
        if condition:
            sql += f" WHERE {condition}"
        return sql + ";"

    def delete_query(self, condition):
        sql = f"DELETE FROM {self.table_name}"
        if condition:
            sql += f" WHERE {condition}"
        return sql + ";"

    def select_female_under_age(self, age):
        condition = f"age < {age} AND gender = 'female'"
        return self.select([], condition)

    def select_by_age_range(self, min_age, max_age):
        condition = f"age BETWEEN {min_age} AND {max_age}"
        return self.select([], condition)

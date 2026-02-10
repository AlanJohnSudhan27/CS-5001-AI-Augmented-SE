import pytest
from src.app import SudokuSolver

@pytest.fixture
def solver():
    return SudokuSolver()

@pytest.fixture
def solved_board():
    return [
        [5, 3, 4, 6, 7, 8, 9, 1, 2],
        [6, 7, 2, 1, 9, 5, 3, 4, 8],
        [1, 9, 8, 3, 4, 2, 5, 6, 7],
        [8, 5, 9, 7, 6, 1, 4, 2, 3],
        [4, 2, 6, 8, 5, 3, 7, 9, 1],
        [7, 1, 3, 9, 2, 4, 8, 5, 6],
        [9, 6, 1, 5, 3, 7, 2, 8, 4],
        [2, 8, 7, 4, 1, 9, 6, 3, 5],
        [3, 4, 5, 2, 8, 6, 1, 7, 9]
    ]

@pytest.fixture
def empty_board():
    return [[0 for _ in range(9)] for _ in range(9)]

def test_initialization(solver, empty_board):
    assert solver.board == empty_board

def test_solve_valid_board(solver, solved_board):
    solver.board = [row.copy() for row in solved_board]
    assert solver.solve() is True

def test_solve_invalid_board(solver):
    board = [[1 for _ in range(9)] for _ in range(9)]
    solver.board = board
    assert solver.solve() is False

def test_solve_empty_board(solver, empty_board):
    solver.board = empty_board
    assert solver.solve() is True

def test_is_valid(solver, solved_board):
    solver.board = [row.copy() for row in solved_board]
    assert solver._is_valid(0, 0, 5) is True
    assert solver._is_valid(0, 0, 1) is False

def test_generate(solver):
    solver.generate()
    assert all(0 not in row for row in solver.board)
    assert solver.solve() is True

def test_remove_cells(solver, solved_board):
    solver.board = [row.copy() for row in solved_board]
    cells_before = sum(row.count(0) for row in solver.board)
    solver.remove_cells(10)
    cells_after = sum(row.count(0) for row in solver.board)
    assert cells_after - cells_before == 10

def test_fill_diagonal(solver):
    solver._fill_diagonal()
    for i in range(0, 9, 3):
        for row in range(i, i + 3):
            for col in range(i, i + 3):
                assert solver.board[row][col] != 0

def test_fill_subgrid(solver):
    solver._fill_subgrid(0, 0)
    for row in range(3):
        for col in range(3):
            assert solver.board[row][col] != 0

def test_fill_remaining(solver, solved_board):
    solver.board = [row.copy() for row in solved_board]
    for row in range(9):
        for col in range(9):
            solver.board[row][col] = 0
    solver._fill_remaining()
    assert all(0 not in row for row in solver.board)
    assert solver.solve() is True

def test_print_board(capsys, solver, solved_board):
    solver.board = [row.copy() for row in solved_board]
    solver.print_board()
    captured = capsys.readouterr()
    assert "5 3 4" in captured.out
    assert "---" in captured.out

import random
from typing import List, Optional, Tuple

class SudokuSolver:
    """A minimal Sudoku solver using backtracking."""

    def __init__(self, board: Optional[List[List[int]]] = None):
        """Initialize the solver with an optional board.

        Args:
            board: A 9x9 Sudoku board (0 represents empty cells).
        """
        self.board = board if board is not None else [[0 for _ in range(9)] for _ in range(9)]

    def solve(self) -> bool:
        """Solve the Sudoku board using backtracking.

        Returns:
            bool: True if the board was solved, False otherwise.
        """
        for row in range(9):
            for col in range(9):
                if self.board[row][col] == 0:
                    for num in range(1, 10):
                        if self._is_valid(row, col, num):
                            self.board[row][col] = num
                            if self.solve():
                                return True
                            self.board[row][col] = 0
                    return False
        return True

    def _is_valid(self, row: int, col: int, num: int) -> bool:
        """Check if placing 'num' at (row, col) is valid.

        Args:
            row: Row index (0-8).
            col: Column index (0-8).
            num: Number to check (1-9).

        Returns:
            bool: True if valid, False otherwise.
        """
        # Check row and column
        for i in range(9):
            if self.board[row][i] == num or self.board[i][col] == num:
                return False

        # Check 3x3 subgrid
        subgrid_row, subgrid_col = 3 * (row // 3), 3 * (col // 3)
        for i in range(subgrid_row, subgrid_row + 3):
            for j in range(subgrid_col, subgrid_col + 3):
                if self.board[i][j] == num:
                    return False

        return True

    def generate(self) -> None:
        """Generate a random solvable Sudoku board."""
        self.board = [[0 for _ in range(9)] for _ in range(9)]
        self._fill_diagonal()
        self._fill_remaining()

    def _fill_diagonal(self) -> None:
        """Fill the diagonal 3x3 subgrids with random valid numbers."""
        for i in range(0, 9, 3):
            self._fill_subgrid(i, i)

    def _fill_subgrid(self, row: int, col: int) -> None:
        """Fill a 3x3 subgrid with random valid numbers."""
        nums = list(range(1, 10))
        random.shuffle(nums)
        for i in range(3):
            for j in range(3):
                for num in nums:
                    if self._is_valid(row + i, col + j, num):
                        self.board[row + i][col + j] = num
                        nums.remove(num)
                        break

    def _fill_remaining(self) -> None:
        """Fill the remaining cells with random valid numbers."""
        for row in range(9):
            for col in range(9):
                if self.board[row][col] == 0:
                    nums = list(range(1, 10))
                    random.shuffle(nums)
                    for num in nums:
                        if self._is_valid(row, col, num):
                            self.board[row][col] = num
                            break

    def remove_cells(self, cells_to_remove: int = 40) -> None:
        """Remove cells from the board to create a puzzle.

        Args:
            cells_to_remove: Number of cells to remove (default: 40).
        """
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)
        for i, j in cells[:cells_to_remove]:
            self.board[i][j] = 0

    def print_board(self) -> None:
        """Print the Sudoku board in a readable format."""
        for i in range(9):
            if i % 3 == 0 and i != 0:
                print("-" * 21)
            for j in range(9):
                if j % 3 == 0 and j != 0:
                    print("|", end=" ")
                print(self.board[i][j] if self.board[i][j] != 0 else ".", end=" ")
            print()

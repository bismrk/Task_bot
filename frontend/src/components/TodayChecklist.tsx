import React, { useState, useEffect, useMemo } from 'react';
import type { TaskCreate, TaskPriority, TaskRead } from '../api/types';
import { TaskCard } from './TaskCard';
import { TaskCreationModal } from './TaskCreationModal';
import { createTask, deleteTask, toggleTask } from '../api/client';
import { CheckCircle2, ListTodo, Plus, AlertCircle } from 'lucide-react';

interface TodayChecklistProps {
  initialTasks: TaskRead[];
  onTasksChanged?: (tasks: TaskRead[]) => void;
  targetDate?: string;
  userTimezone?: string;
}

const PRIORITY_ORDER: Record<TaskPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

export const TodayChecklist: React.FC<TodayChecklistProps> = ({
  initialTasks,
  onTasksChanged,
  targetDate,
  userTimezone,
}) => {
  const [tasks, setTasks] = useState<TaskRead[]>(initialTasks);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  // Sync internal state when props update
  useEffect(() => {
    setTasks(initialTasks);
  }, [initialTasks]);

  const notifyChange = (updatedTasks: TaskRead[]) => {
    setTasks(updatedTasks);
    onTasksChanged?.(updatedTasks);
  };

  // Sort tasks: `todo` tasks first by priority (high -> medium -> low), followed by `done` tasks
  const sortedTasks = useMemo(() => {
    return [...tasks].sort((a, b) => {
      // 1. Todo before done
      if (a.status !== b.status) {
        if (a.status === 'todo') return -1;
        if (b.status === 'todo') return 1;
      }
      // 2. Priority order for same status
      const pDiff = (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1);
      if (pDiff !== 0) return pDiff;

      // 3. Fallback to id
      return a.id - b.id;
    });
  }, [tasks]);

  const totalCount = tasks.length;
  const doneCount = tasks.filter((t) => t.status === 'done').length;
  const progressText = `${doneCount} з ${totalCount} виконано`;
  const percentage = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  // Optimistic Toggle (REQ-TMA-01)
  const handleToggle = async (taskId: number) => {
    const previous = [...tasks];
    const optimistic = tasks.map((t) =>
      t.id === taskId
        ? { ...t, status: (t.status === 'done' ? 'todo' : 'done') as TaskRead['status'] }
        : t
    );
    notifyChange(optimistic);

    try {
      const serverUpdated = await toggleTask(taskId);
      const synced = tasks.map((t) => (t.id === taskId ? serverUpdated : t));
      notifyChange(synced);
    } catch {
      // Rollback to prior state and show error notification
      notifyChange(previous);
      setErrorToast('Не вдалося змінити статус завдання. Спробуйте ще раз.');
      setTimeout(() => setErrorToast(null), 4000);
    }
  };

  // Optimistic Delete
  const handleDelete = async (taskId: number) => {
    const previous = [...tasks];
    const optimistic = tasks.filter((t) => t.id !== taskId);
    notifyChange(optimistic);

    try {
      await deleteTask(taskId);
    } catch {
      // Rollback to prior state and show error notification
      notifyChange(previous);
      setErrorToast('Не вдалося видалити завдання. Спробуйте ще раз.');
      setTimeout(() => setErrorToast(null), 4000);
    }
  };

  // Create Task
  const handleCreateTask = async (payload: TaskCreate) => {
    const created = await createTask(payload);
    notifyChange([...tasks, created]);
  };

  return (
    <div className="space-y-4">
      {/* Header with Progress Counter & Visual Progress Bar */}
      <div className="p-4 rounded-2xl bg-secondary/60 border border-black/5 dark:border-white/5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListTodo className="w-5 h-5 text-primary" />
            <span className="font-semibold text-sm">Сьогоднішній план</span>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
            {progressText}
          </span>
        </div>

        {/* Visual Progress Bar */}
        <div className="space-y-1">
          <div className="w-full bg-black/10 dark:bg-white/10 h-2.5 rounded-full overflow-hidden">
            <div
              className="bg-primary h-full rounded-full transition-all duration-300 ease-out"
              style={{ width: `${percentage}%` }}
            />
          </div>
          <div className="flex justify-end text-[10px] text-muted font-medium">
            <span>{percentage}% завершено</span>
          </div>
        </div>
      </div>

      {/* Error notification banner / toast on rollback */}
      {errorToast && (
        <div className="p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-red-500 text-xs flex items-center justify-between animate-in fade-in duration-150">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorToast}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorToast(null)}
            className="p-1 hover:opacity-80 text-sm font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* Task List or Empty State */}
      {totalCount === 0 ? (
        <div className="py-12 px-6 rounded-2xl bg-secondary/40 border border-dashed border-black/10 dark:border-white/10 flex flex-col items-center justify-center text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div className="space-y-1 max-w-xs">
            <h3 className="font-semibold text-sm text-foreground">На сьогодні завдань немає</h3>
            <p className="text-xs text-muted">
              Додайте нове завдання за допомогою кнопки нижче, щоб організувати свій день.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {sortedTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onToggle={handleToggle}
              onDelete={handleDelete}
              userTimezone={userTimezone}
            />
          ))}
        </div>
      )}

      {/* Floating Action Button (FAB) / Add Task Button */}
      <div className="pt-2">
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="w-full py-3.5 px-4 rounded-2xl bg-primary text-primary-foreground font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-primary/25 hover:opacity-95 active:scale-[0.98] transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>+ Додати завдання</span>
        </button>
      </div>

      {/* Task Creation Modal */}
      <TaskCreationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateTask}
        targetDate={targetDate}
        userTimezone={userTimezone}
      />
    </div>
  );
};

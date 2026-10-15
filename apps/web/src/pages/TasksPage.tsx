import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckSquare,
  Search,
  Check,
  Clock,
  User as UserIcon,
  MoreVertical,
  Plus,
  AlertCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  X,
  Eye,
  Edit3,
  Trash2,
  UserPlus,
  ArrowUpDown,
  ExternalLink,
  Sparkles,
} from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useAuthStore } from '../stores/useAuthStore';
import { meetingsApi } from '../api/meetings';
import { intelligenceApi } from '../api/intelligence';
import { workspaceApi } from '../api/workspace';
import { ActionItem, ActionItemStatus, PriorityLevel, Meeting, WorkspaceMember } from '../types';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Skeleton } from '../components/ui/Skeleton';
import { Modal } from '../components/ui/Modal';
import { Avatar } from '../components/ui/Avatar';

type TaskWithMeta = ActionItem & {
  meeting_title?: string;
  isOverdue?: boolean;
};

export const TasksPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeWorkspace } = useWorkspaceStore();
  const { user: currentUser } = useAuthStore();

  const [actionItems, setActionItems] = useState<TaskWithMeta[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [metrics, setMetrics] = useState({ total: 0, myTasks: 0, overdue: 0, completed: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [assigneeFilter, setAssigneeFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [meetingFilter, setMeetingFilter] = useState<string>('ALL');
  const [dueDateFilter, setDueDateFilter] = useState<string>('ALL');

  // Sorting
  const [sortBy, setSortBy] = useState<'due_date' | 'priority' | 'status' | 'created_at' | 'title'>('due_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Selected Task for Details View
  const [selectedTask, setSelectedTask] = useState<TaskWithMeta | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Edit Task State
  const [editingTask, setEditingTask] = useState<TaskWithMeta | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editAssigneeName, setEditAssigneeName] = useState('');
  const [editPriority, setEditPriority] = useState<PriorityLevel>(PriorityLevel.MEDIUM);
  const [editStatus, setEditStatus] = useState<ActionItemStatus>(ActionItemStatus.OPEN);
  const [editDueDate, setEditDueDate] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Create Task State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createMeetingId, setCreateMeetingId] = useState('');
  const [createTitle, setCreateTitle] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [createAssigneeName, setCreateAssigneeName] = useState('');
  const [createPriority, setCreatePriority] = useState<PriorityLevel>(PriorityLevel.MEDIUM);
  const [createDueDate, setCreateDueDate] = useState('');

  // Active Dropdown Row ID
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const fetchTaskData = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const isMyTasks = assigneeFilter === 'MY_TASKS';
      const [fetchedMeetings, fetchedMembers, metricsRes, actionItemsRes] = await Promise.all([
        meetingsApi.getMeetings({ workspace_id: activeWorkspace.id }).catch(() => []),
        workspaceApi.getMembers(activeWorkspace.id).catch(() => []),
        intelligenceApi.getActionItemMetrics(activeWorkspace.id).catch(() => ({ total: 0, my_tasks: 0, overdue: 0, completed: 0 })),
        intelligenceApi.getActionItems({
          workspace_id: activeWorkspace.id,
          search: searchTerm,
          status: statusFilter,
          assignee_name: isMyTasks ? 'MY_TASKS' : assigneeFilter,
          assignee_id: isMyTasks && currentUser ? currentUser.id : undefined,
          priority: priorityFilter,
          meeting_id: meetingFilter,
          due_date_filter: dueDateFilter,
          page: currentPage,
          page_size: pageSize,
          sort_by: sortBy,
          sort_order: sortOrder,
        }),
      ]);

      setMeetings(fetchedMeetings);
      setMembers(fetchedMembers);
      setMetrics({
        total: metricsRes.total,
        myTasks: metricsRes.my_tasks,
        overdue: metricsRes.overdue,
        completed: metricsRes.completed,
      });

      const now = new Date();
      const itemsWithMeta: TaskWithMeta[] = actionItemsRes.items.map((item) => {
        const meetingObj = fetchedMeetings.find((m) => m.id === item.meeting_id);
        const isOverdue =
          !!item.due_date &&
          new Date(item.due_date) < now &&
          item.status !== ActionItemStatus.COMPLETED &&
          item.status !== ActionItemStatus.CANCELLED;

        return {
          ...item,
          meeting_title: item.meeting_title || meetingObj?.title || 'Workspace Meeting',
          isOverdue,
        };
      });

      setActionItems(itemsWithMeta);
      setTotalCount(actionItemsRes.total);
      setTotalPages(actionItemsRes.total_pages);
    } catch (err: any) {
      console.error('[ActionItems] Failed to fetch tasks:', err);
      const detail = err?.response?.data?.detail;
      const status = err?.response?.status;
      if (detail && status) {
        setError(`${detail} (HTTP ${status})`);
      } else {
        setError(detail || err?.message || 'Failed to load workspace action items. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTaskData();
  }, [
    activeWorkspace?.id,
    searchTerm,
    statusFilter,
    assigneeFilter,
    priorityFilter,
    meetingFilter,
    dueDateFilter,
    sortBy,
    sortOrder,
    currentPage,
    pageSize,
  ]);

  // Click outside listener for dropdown action menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle direct Status Toggle
  const handleToggleStatus = async (item: TaskWithMeta, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const newStatus =
      item.status === ActionItemStatus.COMPLETED
        ? ActionItemStatus.OPEN
        : ActionItemStatus.COMPLETED;

    // Optimistic update
    setActionItems((prev) =>
      prev.map((i) => (i.id === item.id ? { ...i, status: newStatus } : i))
    );

    try {
      await intelligenceApi.updateActionItemStatus(item.id, newStatus);
      fetchTaskData();
    } catch (err) {
      console.error('Failed to update status', err);
      fetchTaskData();
    }
  };

  // Quick Action Handlers
  const handleOpenDetails = (item: TaskWithMeta) => {
    setSelectedTask(item);
    setIsDetailsOpen(true);
    setActiveMenuId(null);
  };

  const handleOpenEdit = (item: TaskWithMeta) => {
    setEditingTask(item);
    setEditTitle(item.title || item.description || '');
    setEditDescription(item.description || '');
    setEditAssigneeName(item.assignee_name || '');
    setEditPriority(item.priority || PriorityLevel.MEDIUM);
    setEditStatus(item.status || ActionItemStatus.OPEN);
    setEditDueDate(item.due_date ? new Date(item.due_date).toISOString().slice(0, 10) : '');
    setIsEditOpen(true);
    setActiveMenuId(null);
  };

  const handleSaveEdit = async () => {
    if (!editingTask) return;
    setActionLoading(true);
    try {
      await intelligenceApi.updateActionItem(editingTask.id, {
        title: editTitle,
        description: editDescription,
        assignee_name: editAssigneeName,
        priority: editPriority,
        status: editStatus,
        due_date: editDueDate ? new Date(editDueDate).toISOString() : undefined,
      });

      setIsEditOpen(false);
      fetchTaskData();
    } catch (err) {
      console.error('Failed to save task edits', err);
      alert('Failed to update task. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteTask = async (item: TaskWithMeta) => {
    if (!window.confirm(`Are you sure you want to delete "${item.title || item.description}"?`)) {
      return;
    }
    setActiveMenuId(null);
    if (selectedTask?.id === item.id) {
      setIsDetailsOpen(false);
      setSelectedTask(null);
    }

    try {
      await intelligenceApi.deleteActionItem(item.id);
      fetchTaskData();
    } catch (err) {
      console.error('Failed to delete task', err);
      fetchTaskData();
    }
  };

  const handleCreateTask = async () => {
    if (!createMeetingId || !createTitle.trim()) {
      alert('Please select a meeting and enter a task title.');
      return;
    }
    setActionLoading(true);
    try {
      await intelligenceApi.createActionItem(createMeetingId, {
        title: createTitle,
        description: createDescription,
        assignee_name: createAssigneeName,
        priority: createPriority,
        due_date: createDueDate ? new Date(createDueDate).toISOString() : undefined,
        status: ActionItemStatus.OPEN,
      });

      setIsCreateOpen(false);
      setCreateTitle('');
      setCreateDescription('');
      setCreateAssigneeName('');
      setCreatePriority(PriorityLevel.MEDIUM);
      setCreateDueDate('');
      fetchTaskData();
    } catch (err) {
      console.error('Failed to create task', err);
      alert('Failed to create task. Please ensure you have appropriate permissions.');
    } finally {
      setActionLoading(false);
    }
  };

  // Unique lists for filters
  const uniqueAssignees = useMemo(() => {
    const set = new Set<string>();
    actionItems.forEach((item) => {
      if (item.assignee_name) set.add(item.assignee_name);
    });
    members.forEach((m) => {
      if (m.user?.full_name) set.add(m.user.full_name);
    });
    return Array.from(set);
  }, [actionItems, members]);

  // Helper for priority badge styling
  const getPriorityBadge = (priority?: PriorityLevel) => {
    switch (priority) {
      case PriorityLevel.URGENT:
        return (
          <span className="inline-flex items-center space-x-1.5 bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444] px-2.5 py-0.5 rounded-full text-[12px] font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444] animate-pulse" />
            <span>Urgent</span>
          </span>
        );
      case PriorityLevel.HIGH:
        return (
          <span className="inline-flex items-center space-x-1.5 bg-[#F59E0B]/15 border border-[#F59E0B]/40 text-[#F59E0B] px-2.5 py-0.5 rounded-full text-[12px] font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" />
            <span>High</span>
          </span>
        );
      case PriorityLevel.MEDIUM:
        return (
          <span className="inline-flex items-center space-x-1.5 bg-[#3B82F6]/15 border border-[#3B82F6]/40 text-[#3B82F6] px-2.5 py-0.5 rounded-full text-[12px] font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
            <span>Medium</span>
          </span>
        );
      case PriorityLevel.LOW:
      default:
        return (
          <span className="inline-flex items-center space-x-1.5 bg-[#123456] border border-[#1D4E78] text-[#8FA4BD] px-2.5 py-0.5 rounded-full text-[12px] font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#8FA4BD]" />
            <span>Low</span>
          </span>
        );
    }
  };

  // Helper for status badge styling
  const getStatusBadge = (item: TaskWithMeta) => {
    const now = new Date();
    const isOverdue =
      !!item.due_date &&
      new Date(item.due_date) < now &&
      item.status !== ActionItemStatus.COMPLETED &&
      item.status !== ActionItemStatus.CANCELLED;

    if (isOverdue) {
      return <Badge variant="danger" size="sm">Overdue</Badge>;
    }

    switch (item.status) {
      case ActionItemStatus.COMPLETED:
        return <Badge variant="success" size="sm">Completed</Badge>;
      case ActionItemStatus.IN_PROGRESS:
        return <Badge variant="violet" size="sm">In Progress</Badge>;
      case ActionItemStatus.CANCELLED:
        return <Badge variant="default" size="sm">Cancelled</Badge>;
      case ActionItemStatus.OPEN:
      default:
        return <Badge variant="primary" size="sm">Open</Badge>;
    }
  };

  const formatSeconds = (sec?: number) => {
    if (sec === undefined || sec === null) return null;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6 animate-fade-in text-[#F8FAFC]">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC] tracking-tight">
            Action Items & Tasks
          </h1>
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1">
            Aggregated tasks automatically extracted from your workspace meetings.
          </p>
        </div>

        <Button
          onClick={() => {
            if (meetings.length > 0) {
              setCreateMeetingId(meetings[0].id);
            }
            setIsCreateOpen(true);
          }}
          icon={<Plus className="w-4 h-4" />}
          className="shrink-0"
        >
          Create Task
        </Button>
      </div>

      {/* 2. Compact Summary Metrics (4 Cards) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Tasks */}
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-4 flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-[#8FA4BD]">Total Tasks</p>
            <p className="text-[24px] sm:text-[28px] font-extrabold text-[#F8FAFC] mt-0.5">{metrics.total}</p>
          </div>
          <div className="p-3 rounded-xl bg-[#3B82F6]/15 text-[#3B82F6] border border-[#3B82F6]/30">
            <CheckSquare className="w-5 h-5" />
          </div>
        </Card>

        {/* My Tasks */}
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-4 flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-[#8FA4BD]">My Tasks</p>
            <p className="text-[24px] sm:text-[28px] font-extrabold text-[#F8FAFC] mt-0.5">{metrics.myTasks}</p>
          </div>
          <div className="p-3 rounded-xl bg-[#818CF8]/15 text-[#818CF8] border border-[#6366F1]/30">
            <UserIcon className="w-5 h-5" />
          </div>
        </Card>

        {/* Overdue */}
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-4 flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-[#8FA4BD]">Overdue</p>
            <p className={`text-[24px] sm:text-[28px] font-extrabold mt-0.5 ${metrics.overdue > 0 ? 'text-[#EF4444]' : 'text-[#F8FAFC]'}`}>
              {metrics.overdue}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30">
            <Clock className="w-5 h-5" />
          </div>
        </Card>

        {/* Completed */}
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-4 flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-[#8FA4BD]">Completed</p>
            <p className="text-[24px] sm:text-[28px] font-extrabold text-[#22C55E] mt-0.5">{metrics.completed}</p>
          </div>
          <div className="p-3 rounded-xl bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30">
            <Check className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* 3. Interactive Toolbar */}
      <Card className="bg-[#102C4D] border border-[#1D4E78] p-4 space-y-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Search Bar */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[#8FA4BD] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search tasks, descriptions, assignees, or meetings..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] placeholder-[#8FA4BD] text-[13px] sm:text-[14px] rounded-xl pl-10 pr-4 py-2.5 focus:outline-none focus:border-[#3B82F6] transition-colors"
            />
            {searchTerm && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setCurrentPage(1);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8FA4BD] hover:text-[#F8FAFC]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Sort Controls */}
          <div className="flex items-center space-x-2 shrink-0">
            <span className="text-[12px] text-[#8FA4BD] font-medium hidden sm:inline">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as any);
                setCurrentPage(1);
              }}
              className="bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[13px] rounded-xl px-3 py-2 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="due_date">Due Date</option>
              <option value="priority">Priority</option>
              <option value="status">Status</option>
              <option value="created_at">Created Date</option>
              <option value="title">Title</option>
            </select>
            <button
              onClick={() => {
                setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
                setCurrentPage(1);
              }}
              title={`Sort ${sortOrder === 'asc' ? 'Ascending' : 'Descending'}`}
              className="bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] p-2 rounded-xl hover:bg-[#1D4E78] transition-colors"
            >
              <ArrowUpDown className="w-4 h-4 text-[#8FA4BD]" />
            </button>
          </div>
        </div>

        {/* Filter Dropdowns Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 pt-2 border-t border-[#1D4E78]">
          {/* Status Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-[#8FA4BD] mb-1">STATUS</label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] sm:text-[13px] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="OVERDUE">Overdue</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>

          {/* Assignee Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-[#8FA4BD] mb-1">ASSIGNEE</label>
            <select
              value={assigneeFilter}
              onChange={(e) => {
                setAssigneeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] sm:text-[13px] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="ALL">All Assignees</option>
              <option value="MY_TASKS">Assigned to Me</option>
              <option value="UNASSIGNED">Unassigned</option>
              {uniqueAssignees.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          {/* Priority Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-[#8FA4BD] mb-1">PRIORITY</label>
            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] sm:text-[13px] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="ALL">All Priorities</option>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="URGENT">Urgent</option>
            </select>
          </div>

          {/* Meeting Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-[#8FA4BD] mb-1">SOURCE MEETING</label>
            <select
              value={meetingFilter}
              onChange={(e) => {
                setMeetingFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] sm:text-[13px] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="ALL">All Meetings</option>
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </div>

          {/* Due Date Filter */}
          <div className="col-span-2 sm:col-span-1">
            <label className="block text-[11px] font-semibold text-[#8FA4BD] mb-1">DUE DATE</label>
            <select
              value={dueDateFilter}
              onChange={(e) => {
                setDueDateFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] sm:text-[13px] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#3B82F6]"
            >
              <option value="ALL">All Time</option>
              <option value="OVERDUE">Overdue Only</option>
              <option value="TODAY">Due Today</option>
              <option value="THIS_WEEK">Due This Week</option>
              <option value="THIS_MONTH">Due This Month</option>
              <option value="NO_DUE_DATE">No Due Date</option>
            </select>
          </div>
        </div>
      </Card>

      {/* 4. API Error State with Retry Button */}
      {error && (
        <Card className="p-6 bg-[#EF4444]/10 border border-[#EF4444]/40 text-[#F8FAFC] flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <AlertCircle className="w-6 h-6 text-[#EF4444] shrink-0" />
            <div>
              <h4 className="font-bold text-[16px] text-[#EF4444]">Unable to Load Action Items</h4>
              <p className="text-[13px] text-[#B8C7DA] mt-0.5">{error}</p>
            </div>
          </div>
          <Button variant="danger" size="sm" onClick={fetchTaskData} icon={<RefreshCw className="w-4 h-4" />}>
            Retry API Request
          </Button>
        </Card>
      )}

      {/* 5. Main Data Table Container (TABLE-FIRST DESIGN) */}
      {loading ? (
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-6 space-y-4">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </Card>
      ) : actionItems.length === 0 ? (
        /* 6. Professional Table-Oriented Empty State */
        <Card className="p-16 text-center bg-[#102C4D] border border-[#1D4E78] space-y-4 shadow-xl">
          <div className="w-16 h-16 rounded-full bg-[#123456] border border-[#1D4E78] flex items-center justify-center mx-auto text-[#8FA4BD]">
            <CheckSquare className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">No action items yet</h3>
            <p className="text-[14px] sm:text-[15px] text-[#8FA4BD] mt-1.5 max-w-md mx-auto">
              Action items will automatically appear here after ConvoMind analyzes your meetings.
            </p>
          </div>
          {(searchTerm || statusFilter !== 'ALL' || assigneeFilter !== 'ALL' || priorityFilter !== 'ALL' || meetingFilter !== 'ALL' || dueDateFilter !== 'ALL') && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('ALL');
                setAssigneeFilter('ALL');
                setPriorityFilter('ALL');
                setMeetingFilter('ALL');
                setDueDateFilter('ALL');
                setCurrentPage(1);
              }}
            >
              Reset Filters
            </Button>
          )}
        </Card>
      ) : (
        <Card className="bg-[#102C4D] border border-[#1D4E78] overflow-hidden p-0 shadow-xl">
          {/* Desktop Table View */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#0B2342] border-b border-[#1D4E78] text-[12px] font-bold text-[#8FA4BD] uppercase tracking-wider">
                  <th className="py-3.5 px-4 w-10 text-center">
                    <CheckSquare className="w-4 h-4 mx-auto text-[#8FA4BD]" />
                  </th>
                  <th className="py-3.5 px-4">Task</th>
                  <th className="py-3.5 px-4">Assignee</th>
                  <th className="py-3.5 px-4">Due Date</th>
                  <th className="py-3.5 px-4">Priority</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Source Meeting</th>
                  <th className="py-3.5 px-4 w-12 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D4E78]">
                {actionItems.map((item) => {
                  const isDone = item.status === ActionItemStatus.COMPLETED;
                  const displayTitle = item.title || item.description || 'Action Item';

                  return (
                    <tr
                      key={item.id}
                      onClick={() => handleOpenDetails(item)}
                      className={`group hover:bg-[#123456] transition-colors cursor-pointer text-[14px] ${
                        isDone ? 'bg-[#0A1B35]/60 text-[#8FA4BD]' : 'text-[#F8FAFC]'
                      }`}
                    >
                      {/* Checkbox */}
                      <td className="py-4 px-4 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={(e) => handleToggleStatus(item, e)}
                          className={`w-5 h-5 rounded flex items-center justify-center border transition-colors mx-auto ${
                            isDone
                              ? 'bg-[#22C55E] border-[#22C55E] text-white'
                              : 'border-[#1D4E78] bg-[#123456] hover:border-[#3B82F6]'
                          }`}
                        >
                          {isDone && <Check className="w-3.5 h-3.5 text-white stroke-[3]" />}
                        </button>
                      </td>

                      {/* Task Title & Metadata */}
                      <td className="py-4 px-4 max-w-xs lg:max-w-md">
                        <div className="space-y-1">
                          <p className={`font-semibold leading-snug line-clamp-2 ${isDone ? 'line-through text-[#8FA4BD]' : 'text-[#F8FAFC]'}`}>
                            {displayTitle}
                          </p>
                          <div className="flex flex-wrap items-center gap-2 text-[12px] text-[#8FA4BD]">
                            <span className="inline-flex items-center space-x-1 font-semibold text-[#818CF8] bg-[#6366F1]/15 px-2 py-0.5 rounded border border-[#6366F1]/30 text-[11px]">
                              <Sparkles className="w-3 h-3 text-[#818CF8]" />
                              <span>{item.source_segment_id ? 'AI Extracted' : 'Task'}</span>
                            </span>
                            {item.meeting_title && (
                              <span className="truncate max-w-[160px] text-[#B8C7DA]">
                                · {item.meeting_title}
                              </span>
                            )}
                            {item.timestamp_marker !== undefined && item.timestamp_marker !== null && (
                              <span>· {formatSeconds(item.timestamp_marker)}</span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Assignee */}
                      <td className="py-4 px-4 whitespace-nowrap">
                        {item.assignee_name ? (
                          <div className="flex items-center space-x-2">
                            <Avatar name={item.assignee_name} size="sm" />
                            <span className="font-medium text-[#F8FAFC] text-[13px]">{item.assignee_name}</span>
                          </div>
                        ) : (
                          <span className="text-[13px] text-[#8FA4BD] italic">Unassigned</span>
                        )}
                      </td>

                      {/* Due Date */}
                      <td className="py-4 px-4 whitespace-nowrap text-[13px]">
                        {item.due_date ? (
                          <span
                            className={`flex items-center space-x-1.5 ${
                              item.isOverdue ? 'text-[#EF4444] font-bold' : 'text-[#B8C7DA]'
                            }`}
                          >
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{new Date(item.due_date).toLocaleDateString()}</span>
                          </span>
                        ) : (
                          <span className="text-[#8FA4BD]">--</span>
                        )}
                      </td>

                      {/* Priority */}
                      <td className="py-4 px-4 whitespace-nowrap">{getPriorityBadge(item.priority)}</td>

                      {/* Status */}
                      <td className="py-4 px-4 whitespace-nowrap">{getStatusBadge(item)}</td>

                      {/* Source Meeting */}
                      <td className="py-4 px-4 max-w-[180px]" onClick={(e) => e.stopPropagation()}>
                        {item.meeting_id ? (
                          <button
                            onClick={() =>
                              navigate(
                                `/meetings/${item.meeting_id}?tab=transcript${
                                  item.timestamp_marker !== undefined && item.timestamp_marker !== null
                                    ? `&t=${item.timestamp_marker}`
                                    : ''
                                }`
                              )
                            }
                            className="flex items-center space-x-1.5 text-[13px] font-semibold text-[#3B82F6] hover:text-[#60A5FA] hover:underline truncate"
                          >
                            <span className="truncate">{item.meeting_title || 'View Meeting'}</span>
                            <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                          </button>
                        ) : (
                          <span className="text-[13px] text-[#8FA4BD]">--</span>
                        )}
                      </td>

                      {/* Actions Ellipsis Menu */}
                      <td className="py-4 px-4 text-center relative" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => setActiveMenuId(activeMenuId === item.id ? null : item.id)}
                          className="p-1.5 rounded-lg text-[#8FA4BD] hover:text-[#F8FAFC] hover:bg-[#1D4E78] transition-colors"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>

                        {/* Dropdown Menu Overlay */}
                        {activeMenuId === item.id && (
                          <div
                            ref={menuRef}
                            className="absolute right-4 top-12 z-40 w-48 bg-[#0B2342] border border-[#1D4E78] rounded-xl shadow-2xl py-1.5 text-left text-[13px] animate-fade-in"
                          >
                            <button
                              onClick={() => handleOpenDetails(item)}
                              className="w-full flex items-center space-x-2.5 px-3.5 py-2 text-[#F8FAFC] hover:bg-[#123456] transition-colors"
                            >
                              <Eye className="w-4 h-4 text-[#3B82F6]" />
                              <span>View Details</span>
                            </button>

                            <button
                              onClick={() => handleOpenEdit(item)}
                              className="w-full flex items-center space-x-2.5 px-3.5 py-2 text-[#F8FAFC] hover:bg-[#123456] transition-colors"
                            >
                              <Edit3 className="w-4 h-4 text-[#818CF8]" />
                              <span>Edit Task</span>
                            </button>

                            <button
                              onClick={() => handleToggleStatus(item)}
                              className="w-full flex items-center space-x-2.5 px-3.5 py-2 text-[#F8FAFC] hover:bg-[#123456] transition-colors"
                            >
                              <Check className="w-4 h-4 text-[#22C55E]" />
                              <span>
                                {item.status === ActionItemStatus.COMPLETED ? 'Mark as Open' : 'Mark as Completed'}
                              </span>
                            </button>

                            <button
                              onClick={() => handleOpenEdit(item)}
                              className="w-full flex items-center space-x-2.5 px-3.5 py-2 text-[#F8FAFC] hover:bg-[#123456] transition-colors"
                            >
                              <UserPlus className="w-4 h-4 text-[#F59E0B]" />
                              <span>Reassign / Edit Owner</span>
                            </button>

                            <div className="my-1 border-t border-[#1D4E78]" />

                            <button
                              onClick={() => handleDeleteTask(item)}
                              className="w-full flex items-center space-x-2.5 px-3.5 py-2 text-[#EF4444] hover:bg-[#EF4444]/15 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                              <span>Delete Task</span>
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Tablet & Mobile Responsive Cards View */}
          <div className="md:hidden divide-y divide-[#1D4E78]">
            {actionItems.map((item) => {
              const isDone = item.status === ActionItemStatus.COMPLETED;
              const displayTitle = item.title || item.description || 'Action Item';

              return (
                <div
                  key={item.id}
                  onClick={() => handleOpenDetails(item)}
                  className={`p-4 space-y-3 cursor-pointer ${
                    isDone ? 'bg-[#0A1B35]/50' : 'bg-[#102C4D]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start space-x-3">
                      <button
                        onClick={(e) => handleToggleStatus(item, e)}
                        className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center border transition-colors shrink-0 ${
                          isDone
                            ? 'bg-[#22C55E] border-[#22C55E] text-white'
                            : 'border-[#1D4E78] bg-[#123456]'
                        }`}
                      >
                        {isDone && <Check className="w-3.5 h-3.5 text-white stroke-[3]" />}
                      </button>
                      <div>
                        <p className={`font-semibold text-[15px] leading-snug ${isDone ? 'line-through text-[#8FA4BD]' : 'text-[#F8FAFC]'}`}>
                          {displayTitle}
                        </p>
                        <p className="text-[12px] text-[#8FA4BD] mt-0.5">
                          {item.meeting_title}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0">{getStatusBadge(item)}</div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#1D4E78]/60 text-[12px]">
                    <div className="flex items-center space-x-3">
                      {getPriorityBadge(item.priority)}

                      {item.assignee_name && (
                        <div className="flex items-center space-x-1.5 text-[#B8C7DA]">
                          <Avatar name={item.assignee_name} size="sm" />
                          <span>{item.assignee_name}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center space-x-3">
                      {item.due_date && (
                        <span className={item.isOverdue ? 'text-[#EF4444] font-bold' : 'text-[#8FA4BD]'}>
                          {new Date(item.due_date).toLocaleDateString()}
                        </span>
                      )}

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenEdit(item);
                        }}
                        className="p-1 rounded text-[#8FA4BD] hover:text-[#F8FAFC]"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 7. Pagination Bar */}
          <div className="p-4 bg-[#0B2342] border-t border-[#1D4E78] flex flex-col sm:flex-row items-center justify-between gap-4 text-[13px] text-[#8FA4BD]">
            <div className="flex items-center space-x-3">
              <span>
                Showing <strong className="text-[#F8FAFC]">{totalCount > 0 ? (currentPage - 1) * pageSize + 1 : 0}</strong> to{' '}
                <strong className="text-[#F8FAFC]">{Math.min(currentPage * pageSize, totalCount)}</strong> of{' '}
                <strong className="text-[#F8FAFC]">{totalCount}</strong> tasks
              </span>

              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[12px] rounded-lg px-2 py-1 focus:outline-none"
              >
                <option value={10}>10 per page</option>
                <option value={25}>25 per page</option>
                <option value={50}>50 per page</option>
              </select>
            </div>

            <div className="flex items-center space-x-1.5">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                className="p-1.5 rounded-lg border border-[#1D4E78] bg-[#123456] text-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#1D4E78] transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="px-3 font-semibold text-[#F8FAFC]">
                Page {currentPage} of {totalPages}
              </span>

              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                className="p-1.5 rounded-lg border border-[#1D4E78] bg-[#123456] text-[#F8FAFC] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#1D4E78] transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* 8. Task Details Modal / Drawer */}
      <Modal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        title="Task Details"
        description="Complete metadata, transcript context, and owner information"
        maxWidth="lg"
        footer={
          selectedTask && (
            <div className="flex items-center justify-between w-full">
              <Button variant="danger" size="sm" onClick={() => handleDeleteTask(selectedTask)} icon={<Trash2 />}>
                Delete Task
              </Button>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" onClick={() => setIsDetailsOpen(false)}>
                  Close
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setIsDetailsOpen(false);
                    handleOpenEdit(selectedTask);
                  }}
                  icon={<Edit3 />}
                >
                  Edit Task
                </Button>
              </div>
            </div>
          )
        }
      >
        {selectedTask && (
          <div className="space-y-5 text-[#F8FAFC]">
            {/* Title Banner */}
            <div className="p-4 rounded-xl bg-[#0A1B35] border border-[#1D4E78] space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center space-x-1 text-[12px] font-bold text-[#818CF8] bg-[#6366F1]/20 px-2.5 py-0.5 rounded border border-[#6366F1]/40">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{selectedTask.source_segment_id ? 'AI Extracted Action Item' : 'Workspace Task'}</span>
                </span>
                {getStatusBadge(selectedTask)}
              </div>
              <h3 className="text-[18px] font-bold text-[#F8FAFC] leading-snug">
                {selectedTask.title || selectedTask.description}
              </h3>
            </div>

            {/* Description */}
            {selectedTask.description && selectedTask.description !== selectedTask.title && (
              <div>
                <h4 className="text-[12px] font-bold text-[#8FA4BD] uppercase tracking-wider mb-1">Description</h4>
                <p className="text-[14px] text-[#B8C7DA] leading-relaxed bg-[#123456] p-3 rounded-xl border border-[#1D4E78]">
                  {selectedTask.description}
                </p>
              </div>
            )}

            {/* Grid Metadata */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4 rounded-xl bg-[#0B2342] border border-[#1D4E78] text-[13px]">
              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Assignee</p>
                <p className="font-semibold text-[#F8FAFC] mt-0.5">
                  {selectedTask.assignee_name || 'Unassigned'}
                </p>
              </div>

              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Priority</p>
                <div className="mt-1">{getPriorityBadge(selectedTask.priority)}</div>
              </div>

              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Due Date</p>
                <p className={`font-semibold mt-0.5 ${selectedTask.isOverdue ? 'text-[#EF4444]' : 'text-[#F8FAFC]'}`}>
                  {selectedTask.due_date ? new Date(selectedTask.due_date).toLocaleDateString() : 'No Due Date'}
                </p>
              </div>

              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Status</p>
                <p className="font-semibold text-[#F8FAFC] mt-0.5">{selectedTask.status}</p>
              </div>

              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Transcript Timestamp</p>
                <p className="font-semibold text-[#3B82F6] mt-0.5">
                  {selectedTask.timestamp_marker !== undefined && selectedTask.timestamp_marker !== null
                    ? formatSeconds(selectedTask.timestamp_marker)
                    : 'N/A'}
                </p>
              </div>

              <div>
                <p className="text-[#8FA4BD] text-[11px] font-semibold uppercase">Source Type</p>
                <p className="font-semibold text-[#F8FAFC] mt-0.5">
                  {selectedTask.source_segment_id ? 'AI Pipeline (v1)' : 'Manual Entry'}
                </p>
              </div>
            </div>

            {/* Source Meeting */}
            {selectedTask.meeting_title && (
              <div className="p-4 rounded-xl bg-[#123456] border border-[#1D4E78] flex items-center justify-between gap-4">
                <div>
                  <p className="text-[12px] font-bold text-[#8FA4BD] uppercase">Source Meeting</p>
                  <p className="font-bold text-[#F8FAFC] text-[15px] mt-0.5">{selectedTask.meeting_title}</p>
                </div>

                {selectedTask.meeting_id && (
                  <Button
                    size="sm"
                    onClick={() => {
                      setIsDetailsOpen(false);
                      navigate(
                        `/meetings/${selectedTask.meeting_id}?tab=transcript${
                          selectedTask.timestamp_marker !== undefined && selectedTask.timestamp_marker !== null
                            ? `&t=${selectedTask.timestamp_marker}`
                            : ''
                        }`
                      );
                    }}
                    icon={<ExternalLink className="w-4 h-4" />}
                  >
                    Go to Meeting
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 9. Edit Task Modal */}
      <Modal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title="Edit Task"
        description="Update task details, owner, priority, status, or due date"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end space-x-3 w-full">
            <Button variant="outline" size="sm" onClick={() => setIsEditOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleSaveEdit} isLoading={actionLoading}>
              Save Changes
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">TASK TITLE</label>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">DESCRIPTION</label>
            <textarea
              rows={3}
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">ASSIGNEE NAME</label>
              <input
                type="text"
                value={editAssigneeName}
                onChange={(e) => setEditAssigneeName(e.target.value)}
                placeholder="Assignee name..."
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              />
            </div>

            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">PRIORITY</label>
              <select
                value={editPriority}
                onChange={(e) => setEditPriority(e.target.value as PriorityLevel)}
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              >
                <option value={PriorityLevel.LOW}>Low</option>
                <option value={PriorityLevel.MEDIUM}>Medium</option>
                <option value={PriorityLevel.HIGH}>High</option>
                <option value={PriorityLevel.URGENT}>Urgent</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">STATUS</label>
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value as ActionItemStatus)}
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              >
                <option value={ActionItemStatus.OPEN}>Open</option>
                <option value={ActionItemStatus.IN_PROGRESS}>In Progress</option>
                <option value={ActionItemStatus.COMPLETED}>Completed</option>
                <option value={ActionItemStatus.CANCELLED}>Cancelled</option>
              </select>
            </div>

            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">DUE DATE</label>
              <input
                type="date"
                value={editDueDate}
                onChange={(e) => setEditDueDate(e.target.value)}
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              />
            </div>
          </div>
        </div>
      </Modal>

      {/* 10. Create Task Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Action Item"
        description="Add a task manually to a workspace meeting"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end space-x-3 w-full">
            <Button variant="outline" size="sm" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleCreateTask} isLoading={actionLoading}>
              Create Task
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">ASSOCIATED MEETING *</label>
            <select
              value={createMeetingId}
              onChange={(e) => setCreateMeetingId(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            >
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">TASK TITLE *</label>
            <input
              type="text"
              placeholder="e.g., Send updated project roadmap to stakeholders..."
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">DESCRIPTION</label>
            <textarea
              rows={2}
              placeholder="Add optional notes or execution steps..."
              value={createDescription}
              onChange={(e) => setCreateDescription(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">ASSIGNEE NAME</label>
              <input
                type="text"
                placeholder="Assignee name..."
                value={createAssigneeName}
                onChange={(e) => setCreateAssigneeName(e.target.value)}
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              />
            </div>

            <div>
              <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">PRIORITY</label>
              <select
                value={createPriority}
                onChange={(e) => setCreatePriority(e.target.value as PriorityLevel)}
                className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
              >
                <option value={PriorityLevel.LOW}>Low</option>
                <option value={PriorityLevel.MEDIUM}>Medium</option>
                <option value={PriorityLevel.HIGH}>High</option>
                <option value={PriorityLevel.URGENT}>Urgent</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[12px] font-bold text-[#8FA4BD] mb-1">DUE DATE</label>
            <input
              type="date"
              value={createDueDate}
              onChange={(e) => setCreateDueDate(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-xl px-3.5 py-2.5 focus:outline-none focus:border-[#3B82F6]"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

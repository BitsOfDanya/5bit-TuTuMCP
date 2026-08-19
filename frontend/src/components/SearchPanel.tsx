import {
  ArrowRightLeft,
  Bot,
  Bus,
  CarFront,
  Hotel,
  Palmtree,
  Plane,
  Search,
  Sparkles,
  TramFront,
  TrainFront,
} from "lucide-react";
import { ComponentType, FormEvent, useState } from "react";
import type { LucideProps } from "lucide-react";

type ProductId =
  | "hotels"
  | "avia"
  | "trains"
  | "buses"
  | "suburban"
  | "tours"
  | "cars"
  | "ai"
  | "jarvel";

interface Product {
  id: ProductId;
  label: string;
  Icon: ComponentType<LucideProps>;
  badge?: string;
}

interface SearchPanelProps {
  onOpenAssistant: () => void;
  onStub: (message: string) => void;
}

const products: Product[] = [
  { id: "hotels", label: "Отели", Icon: Hotel },
  { id: "avia", label: "Авиабилеты", Icon: Plane },
  { id: "trains", label: "Ж/д билеты", Icon: TrainFront },
  { id: "buses", label: "Автобусы", Icon: Bus },
  { id: "suburban", label: "Электрички", Icon: TramFront },
  { id: "tours", label: "Туры", Icon: Palmtree, badge: "Кешбэк до 7%" },
  { id: "cars", label: "Аренда авто", Icon: CarFront },
  { id: "ai", label: "ИИ-помощник", Icon: Sparkles, badge: "ИИ-помощник" },
  { id: "jarvel", label: "Джарвел", Icon: Bot },
];

const searchLabels: Record<ProductId, string> = {
  hotels: "Найти отели",
  avia: "Найти авиабилеты",
  trains: "Найти ж/д билеты",
  buses: "Найти автобусы",
  suburban: "Найти электрички",
  tours: "Найти туры",
  cars: "Найти авто",
  ai: "Спросить помощника",
  jarvel: "Открыть Джарвела",
};

export function SearchPanel({ onOpenAssistant, onStub }: SearchPanelProps) {
  const [activeProduct, setActiveProduct] = useState<ProductId>("avia");

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeProduct === "jarvel") {
      onOpenAssistant();
      return;
    }
    onStub(searchLabels[activeProduct] + ": поиск пока работает как демонстрация");
  }

  function handleProductSelect(productId: ProductId) {
    setActiveProduct(productId);
    if (productId === "jarvel") {
      onOpenAssistant();
    }
  }

  return (
    <>
      <div className="product-tabs" role="tablist" aria-label="Сервисы путешествий">
        {products.map(({ id, label, Icon, badge }) => (
          <button
            className={activeProduct === id ? "product-tab active" : "product-tab"}
            key={id}
            type="button"
            role="tab"
            aria-selected={activeProduct === id}
            onClick={() => handleProductSelect(id)}
          >
            <span className="product-icon-wrap">
              {badge ? <small>{badge}</small> : null}
              <Icon size={31} strokeWidth={2.4} aria-hidden="true" />
            </span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      <form className="travel-search" onSubmit={handleSearch}>
        <SearchField id="from" label="Откуда" placeholder="Москва" />
        <button className="swap-button" type="button" aria-label="Поменять города местами">
          <ArrowRightLeft size={17} aria-hidden="true" />
        </button>
        <SearchField id="to" label="Куда" placeholder="Санкт-Петербург" />
        <SearchField id="departure" label="Когда" placeholder="Сегодня" />
        <SearchField id="return" label="Обратно" placeholder="Завтра" />
        <SearchField id="passengers" label="Кто летит" placeholder="1 пассажир, эконом" />
        <button className="search-button" type="submit">
          <Search size={18} aria-hidden="true" />
          {searchLabels[activeProduct]}
        </button>
      </form>

      <div className="search-extras">
        <div className="suggestion-groups">
          <span>Москва</span>
          <span>Санкт-Петербург</span>
          <span>Сегодня</span>
          <span>Завтра</span>
        </div>
        <label className="hotel-toggle">
          <span>Искать отели в новой вкладке</span>
          <input type="checkbox" defaultChecked />
          <span className="toggle-ui" aria-hidden="true" />
        </label>
      </div>
    </>
  );
}

function SearchField({
  id,
  label,
  placeholder,
}: {
  id: string;
  label: string;
  placeholder: string;
}) {
  return (
    <label className="search-field" htmlFor={id}>
      <span>{label}</span>
      <input id={id} name={id} placeholder={placeholder} />
    </label>
  );
}

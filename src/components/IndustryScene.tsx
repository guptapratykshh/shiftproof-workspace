import { useId, type ReactNode } from "react";
import { industries } from "../lib/industries";
import { usePreferences } from "../lib/preferences";
import { FactoryScene } from "./FactoryScene";

type Industry = (typeof industries)[number]["id"];
const pigment = {
  top: "#c0a0e1",
  front: "#9b7bb7",
  side: "#785990",
  accent: "#ae82df",
  pale: "#e1cff5",
  dark: "#493457",
  metal: "#8a739e",
};

// A shared projection keeps all seven new workplaces on the factory's platform.
const point = (x: number, y: number, z = 0) => [
  166 + x - y * 0.75,
  111 + x * 0.34 + y * 0.68 - z,
];
const polygon = (...points: number[][]) =>
  points.map((p) => p.join(",")).join(" ");

function Block({
  x,
  y,
  w,
  d,
  h,
  z = 0,
  top = pigment.top,
  front = pigment.front,
  side = pigment.side,
}: {
  x: number;
  y: number;
  w: number;
  d: number;
  h: number;
  z?: number;
  top?: string;
  front?: string;
  side?: string;
}) {
  return (
    <g>
      <polygon
        points={polygon(
          point(x, y + d, z),
          point(x + w, y + d, z),
          point(x + w, y + d, z + h),
          point(x, y + d, z + h),
        )}
        fill={front}
      />
      <polygon
        points={polygon(
          point(x + w, y, z),
          point(x + w, y + d, z),
          point(x + w, y + d, z + h),
          point(x + w, y, z + h),
        )}
        fill={side}
      />
      <polygon
        points={polygon(
          point(x, y, z + h),
          point(x + w, y, z + h),
          point(x + w, y + d, z + h),
          point(x, y + d, z + h),
        )}
        fill={top}
      />
    </g>
  );
}

function Face({
  x,
  y,
  z = 0,
  children,
}: {
  x: number;
  y: number;
  z?: number;
  children: ReactNode;
}) {
  const [px, py] = point(x, y, z);
  return <g transform={`matrix(1 .34 0 -1 ${px} ${py})`}>{children}</g>;
}

function Cylinder({
  x,
  y,
  z = 0,
  r,
  h,
  open = false,
}: {
  x: number;
  y: number;
  z?: number;
  r: number;
  h: number;
  open?: boolean;
}) {
  const [cx, cy] = point(x, y, z);
  return (
    <g>
      <path
        d={`M${cx - r} ${cy - h}v${h}a${r} ${r * 0.4} 0 0 0 ${r * 2} 0v-${h}Z`}
        fill={pigment.front}
      />
      <path
        d={`M${cx + r * 0.35} ${cy - h}v${h - 1}a${r} ${r * 0.4} 0 0 0 ${r * 0.65} ${-r * 0.12}v-${h}Z`}
        fill={pigment.side}
        opacity=".6"
      />
      <ellipse cx={cx} cy={cy - h} rx={r} ry={r * 0.4} fill={pigment.pale} />
      {open && (
        <ellipse
          cx={cx}
          cy={cy - h}
          rx={r - 4}
          ry={r * 0.4 - 3}
          fill={pigment.dark}
        />
      )}
    </g>
  );
}

function Crate({
  x,
  y,
  z = 0,
  w = 28,
  d = 24,
  h = 26,
}: {
  x: number;
  y: number;
  z?: number;
  w?: number;
  d?: number;
  h?: number;
}) {
  return (
    <g>
      <Block
        {...{ x, y, z, w, d, h }}
        top="#c1a1e2"
        front="#a085b7"
        side="#836797"
      />
      <Face x={x} y={y + d} z={z}>
        <path
          d={`M${w * 0.48} ${h}v-9`}
          stroke={pigment.pale}
          strokeWidth="5"
          opacity=".65"
        />
        <path
          d={`M5 8h${w * 0.35}`}
          stroke={pigment.pale}
          strokeWidth="4"
          opacity=".75"
        />
      </Face>
    </g>
  );
}

function Bench({
  x,
  y,
  w,
  d,
  h,
}: {
  x: number;
  y: number;
  w: number;
  d: number;
  h: number;
}) {
  return (
    <g>
      {[0, w - 7].flatMap((dx) =>
        [0, d - 7].map((dy) => (
          <Block
            key={`${dx}-${dy}`}
            x={x + dx}
            y={y + dy}
            w={7}
            d={7}
            h={h}
            top={pigment.metal}
          />
        )),
      )}
      <Block
        x={x - 4}
        y={y - 3}
        w={w + 8}
        d={d + 6}
        h={8}
        z={h}
        top={pigment.pale}
      />
    </g>
  );
}

function Maintenance() {
  const gear = Array.from({ length: 40 }, (_, i) => {
    const angle = (i * Math.PI) / 20,
      radius = i % 4 < 2 ? 25 : 20;
    return [35 + Math.cos(angle) * radius, 33 + Math.sin(angle) * radius];
  });
  return (
    <g>
      <Block
        x={170}
        y={16}
        w={50}
        d={8}
        h={94}
        front={pigment.dark}
        top={pigment.metal}
      />
      <Face x={176} y={25} z={20}>
        {[0, 18].map((x) => (
          <path
            key={x}
            d={`M${x + 5} 6v38m-5 8v-8l5-5 5 5v8`}
            stroke={pigment.pale}
            strokeWidth="5"
            fill="none"
            strokeLinecap="round"
          />
        ))}
      </Face>
      <Bench x={29} y={30} w={97} d={53} h={22} />
      <Block
        x={42}
        y={38}
        z={30}
        w={68}
        d={36}
        h={66}
        top="#ab90c4"
        front="#79618e"
      />
      <Face x={42} y={75} z={30}>
        <polygon points={polygon(...gear)} fill={pigment.accent} />
        <circle cx="35" cy="33" r="13" fill={pigment.pale} />
        <circle cx="35" cy="33" r="7" fill={pigment.dark} />
        <circle cx="9" cy="58" r="2" fill={pigment.pale} />
        <circle cx="59" cy="8" r="2" fill={pigment.pale} />
      </Face>
      <Block x={151} y={73} w={60} d={35} h={37} top={pigment.accent} />
      <Face x={151} y={109}>
        <path
          d="M5 12h50M5 24h50"
          stroke={pigment.dark}
          strokeWidth="2"
          opacity=".65"
        />
        <path d="M24 17h13M24 29h13" stroke={pigment.pale} strokeWidth="3" />
      </Face>
      <Block
        x={170}
        y={81}
        z={37}
        w={20}
        d={7}
        h={8}
        front={pigment.dark}
        side={pigment.dark}
      />
      <g transform="matrix(1 .34 -.75 .68 166 103)">
        <path
          d="M38 104 80 92M82 92l12-8 8 6-10 9-10-7"
          fill="none"
          stroke={pigment.side}
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d="M38 101 80 89M82 89l12-8 8 6-10 9-10-7"
          fill="none"
          stroke={pigment.pale}
          strokeWidth="7"
          strokeLinecap="round"
        />
      </g>
    </g>
  );
}

function Warehousing() {
  return (
    <g>
      {[24, 100, 185].map((x) => (
        <Block
          key={x}
          x={x}
          y={22}
          w={6}
          d={6}
          h={111}
          top={pigment.metal}
          front={pigment.side}
        />
      ))}
      {[8, 51, 94].map((z) => (
        <g key={z}>
          <Block
            x={21}
            y={18}
            z={z}
            w={173}
            d={34}
            h={5}
            top="#a187ba"
            front={pigment.dark}
          />
          {[34, 87, 140].map((x) => (
            <Crate key={x} x={x} y={24} z={z + 5} w={34} d={25} h={27} />
          ))}
        </g>
      ))}
      {[24, 100, 185].map((x) => (
        <Block
          key={x}
          x={x}
          y={49}
          w={5}
          d={5}
          h={111}
          top={pigment.pale}
          front={pigment.metal}
        />
      ))}
      <Block x={30} y={82} w={70} d={33} h={6} front={pigment.dark} />
      <Crate x={34} y={85} z={6} w={28} d={26} h={27} />
      <Crate x={65} y={85} z={6} w={28} d={26} h={21} />
      <Block x={146} y={82} w={56} d={32} h={24} z={7} top={pigment.accent} />
      <Block x={147} y={86} w={17} d={22} h={18} z={31} front={pigment.dark} />
      <Block x={199} y={81} w={5} d={5} h={63} top={pigment.pale} />
      <Block x={199} y={109} w={5} d={5} h={63} top={pigment.pale} />
      <Block x={199} y={81} w={27} d={5} h={4} z={8} top={pigment.pale} />
      <Block x={199} y={109} w={27} d={5} h={4} z={8} top={pigment.pale} />
      <Face x={146} y={115}>
        {[9, 45].map((x) => (
          <g key={x}>
            <circle cx={x} cy="8" r="9" fill={pigment.dark} />
            <circle cx={x} cy="8" r="4" fill={pigment.top} />
          </g>
        ))}
      </Face>
    </g>
  );
}

function Quality() {
  return (
    <g>
      <Block
        x={157}
        y={18}
        w={51}
        d={6}
        h={84}
        z={19}
        top={pigment.pale}
        front={pigment.side}
      />
      <Face x={163} y={25} z={31}>
        <rect x="0" y="0" width="39" height="62" rx="2" fill={pigment.pale} />
        <path
          d="M9 45h22M9 36h22M9 27h13"
          stroke={pigment.front}
          strokeWidth="3"
        />
        <path
          d="m11 14 6-5 12 14"
          stroke={pigment.side}
          strokeWidth="4"
          fill="none"
        />
      </Face>
      <Bench x={36} y={53} w={156} d={45} h={51} />
      <Block x={48} y={64} w={48} d={24} h={7} z={59} front={pigment.dark} />
      <Face x={53} y={83} z={66}>
        <path
          d="M15 1h24M30 4c25 23 16 42 4 48"
          fill="none"
          stroke={pigment.side}
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d="M28 8c24 21 15 38 4 42"
          fill="none"
          stroke={pigment.top}
          strokeWidth="7"
        />
        <path
          d="m21 49 13-9m-17 12 6 7"
          stroke={pigment.pale}
          strokeWidth="13"
        />
        <path d="M8 18h29" stroke={pigment.dark} strokeWidth="5" />
        <circle cx="39" cy="24" r="6" fill={pigment.accent} />
      </Face>
      <Block x={131} y={68} z={59} w={49} d={21} h={7} front={pigment.side} />
      {[141, 157, 173].map((x) => (
        <g key={x}>
          <Cylinder x={x} y={77} z={66} r={5} h={27} />
          <Cylinder x={x} y={77} z={92} r={6} h={4} />
        </g>
      ))}
      <Block x={112} y={107} w={60} d={15} h={6} top={pigment.pale} />
      {[125, 143, 161].map((x) => (
        <Cylinder key={x} x={x} y={114} z={6} r={7} h={3} />
      ))}
    </g>
  );
}

function Food() {
  return (
    <g>
      <Block x={42} y={19} w={19} d={19} h={106} top={pigment.pale} />
      <Block x={42} y={19} z={100} w={58} d={18} h={11} top={pigment.accent} />
      <Block x={83} y={30} z={44} w={5} d={5} h={57} front={pigment.pale} />
      <Block x={42} y={39} w={67} d={47} h={9} top={pigment.side} />
      <Cylinder x={78} y={60} z={9} r={34} h={57} open />
      <Block x={74} y={53} z={53} w={28} d={5} h={5} top={pigment.accent} />
      <Face x={51} y={78} z={27}>
        <rect width="19" height="12" rx="2" fill={pigment.pale} />
        <path d="M4 6h11" stroke={pigment.side} strokeWidth="3" />
      </Face>
      <Bench x={133} y={47} w={75} d={57} h={40} />
      {[55, 79].map((y) => (
        <g key={y}>
          <Block x={139} y={y} w={62} d={20} h={4} z={48} top={pigment.side} />
          {[144, 163, 182].map((x) => (
            <Block
              key={x}
              x={x}
              y={y + 3}
              w={15}
              d={14}
              h={8}
              z={52}
              top={pigment.pale}
              front={pigment.top}
            />
          ))}
        </g>
      ))}
      <Cylinder x={63} y={108} r={15} h={22} />
      <Cylinder x={98} y={110} r={11} h={17} />
      <Face x={205} y={59} z={54}>
        <path
          d="M0 0v38"
          stroke={pigment.pale}
          strokeWidth="7"
          strokeLinecap="round"
        />
        <path
          d="M0 3v20"
          stroke={pigment.accent}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cy="2" r="6" fill={pigment.accent} />
      </Face>
    </g>
  );
}

function Construction() {
  return (
    <g>
      <Block x={30} y={22} w={35} d={29} h={9} front={pigment.side} />
      <Block
        x={39}
        y={29}
        w={13}
        d={12}
        h={122}
        top={pigment.pale}
        front={pigment.side}
      />
      <Face x={39} y={42} z={9}>
        {[0, 25, 50, 75].map((z) => (
          <path
            key={z}
            d={`M1 ${z} 12 ${z + 25} 1 ${z + 25} 12 ${z}`}
            stroke={pigment.pale}
            strokeWidth="2"
            fill="none"
          />
        ))}
      </Face>
      <Block x={15} y={21} w={184} d={14} h={8} z={120} top={pigment.accent} />
      <Face x={20} y={36} z={128}>
        <path
          d="M0 0 32 20 174 0M32 20v-20M32 20 70 0M32 20 110 0"
          fill="none"
          stroke={pigment.pale}
          strokeWidth="2.5"
        />
      </Face>
      <Block x={18} y={21} w={21} d={17} h={15} z={105} front={pigment.dark} />
      <Face x={182} y={33} z={50}>
        <path
          d="M0 70V4c0-9 12-9 12 0"
          stroke={pigment.dark}
          strokeWidth="3"
          fill="none"
        />
      </Face>
      <Block x={92} y={67} w={113} d={43} h={10} top={pigment.pale} />
      {[97, 143, 191].map((x) => (
        <Block key={x} x={x} y={71} w={8} d={8} h={69} top={pigment.pale} />
      ))}
      <Block x={91} y={68} w={113} d={41} h={7} z={61} top="#cdb4e9" />
      {[97, 143, 191].map((x) => (
        <Block key={x} x={x} y={101} w={8} d={8} h={59} top={pigment.pale} />
      ))}
      <Block x={95} y={72} w={108} d={35} h={6} z={29} top={pigment.top} />
      {[36, 69].map((x) => {
        const [cx, cy] = point(x, 105);
        return (
          <g key={x}>
            <Block x={x - 8} y={98} w={17} d={16} h={3} top={pigment.side} />
            <path d={`m${cx - 7} ${cy - 2} 7-26 7 26Z`} fill={pigment.accent} />
            <path
              d={`m${cx - 4} ${cy - 12}h8`}
              stroke={pigment.pale}
              strokeWidth="4"
            />
          </g>
        );
      })}
    </g>
  );
}

function Healthcare() {
  const [ivX, ivY] = point(55, 24);
  return (
    <g>
      <Block x={44} y={15} w={25} d={24} h={5} top={pigment.pale} />
      <path
        d={`M${ivX} ${ivY}V${ivY - 113}h24`}
        stroke={pigment.metal}
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
      />
      <rect
        x={ivX + 11}
        y={ivY - 109}
        width="16"
        height="29"
        rx="4"
        fill={pigment.pale}
      />
      <path
        d={`M${ivX + 19} ${ivY - 93}v13q0 25 25 42`}
        stroke={pigment.accent}
        strokeWidth="2"
        fill="none"
      />
      {[64, 164].flatMap((x) =>
        [55, 100].map((y) => (
          <Block
            key={`${x}-${y}`}
            x={x}
            y={y}
            w={7}
            d={7}
            h={25}
            front={pigment.metal}
          />
        )),
      )}
      <Block x={60} y={49} w={115} d={59} h={8} z={24} top={pigment.side} />
      <Block
        x={61}
        y={50}
        w={112}
        d={57}
        h={11}
        z={32}
        top="#e4d7f4"
        front="#c7b0e1"
      />
      <Block x={58} y={48} w={6} d={61} h={62} top={pigment.pale} />
      <Block
        x={69}
        y={60}
        w={23}
        d={36}
        h={7}
        z={43}
        top="#f1e8fb"
        front={pigment.pale}
      />
      <Block
        x={101}
        y={51}
        w={71}
        d={55}
        h={4}
        z={43}
        top={pigment.accent}
        front="#9b71ca"
      />
      <Block x={173} y={49} w={5} d={60} h={47} top={pigment.pale} />
      <Face x={102} y={109} z={40}>
        <path
          d="M0 0v17h56V0M0 9h56"
          fill="none"
          stroke={pigment.pale}
          strokeWidth="3"
        />
      </Face>
      <Block x={197} y={31} w={9} d={15} h={60} top={pigment.pale} />
      <Block
        x={181}
        y={28}
        w={43}
        d={9}
        h={32}
        z={60}
        top={pigment.pale}
        front={pigment.dark}
      />
      <Face x={185} y={38} z={63}>
        <path
          d="M0 12h7l4 8 5-16 5 12 4-4h10"
          fill="none"
          stroke={pigment.pale}
          strokeWidth="2"
        />
        <path d="M0 24h12" stroke={pigment.accent} strokeWidth="2" />
      </Face>
    </g>
  );
}

function Facility() {
  return (
    <g>
      <Block
        x={77}
        y={20}
        w={100}
        d={58}
        h={99}
        top={pigment.pale}
        front="#b497cd"
      />
      <Block x={73} y={16} w={108} d={65} h={7} z={99} top={pigment.pale} />
      {[88, 139].map((x) => (
        <g key={x}>
          <Block x={x} y={33} w={25} d={25} h={15} z={106} top={pigment.top} />
          <Face x={x + 3} y={59} z={109}>
            <path
              d="M0 0h19M0 5h19M0 10h19"
              stroke={pigment.side}
              strokeWidth="2"
            />
          </Face>
        </g>
      ))}
      <Face x={86} y={79} z={36}>
        {[0, 40].flatMap((x) =>
          [0, 31].map((y) => (
            <g key={`${x}-${y}`}>
              <rect x={x} y={y} width="28" height="21" fill={pigment.dark} />
              <path d={`M${x + 4} ${y + 4}h20v13h-20Z`} fill={pigment.top} />
              <path
                d={`M${x + 14} ${y + 4}v13`}
                stroke={pigment.pale}
                strokeWidth="2"
              />
            </g>
          )),
        )}
      </Face>
      <Block x={115} y={76} w={23} d={4} h={29} front={pigment.dark} />
      <Block x={22} y={59} w={37} d={25} h={70} top={pigment.pale} />
      <Face x={27} y={85} z={15}>
        {[0, 8, 16, 24, 32, 40].map((y) => (
          <path
            key={y}
            d={`M0 ${y}h26`}
            stroke={pigment.dark}
            strokeWidth="3"
            opacity=".65"
          />
        ))}
      </Face>
      <Block x={165} y={92} w={48} d={25} h={27} z={5} top={pigment.accent} />
      <Face x={165} y={118}>
        <circle cx="7" cy="5" r="6" fill={pigment.dark} />
        <circle cx="40" cy="5" r="6" fill={pigment.dark} />
        <path
          d="M3 32v17h38V32"
          stroke={pigment.pale}
          strokeWidth="3"
          fill="none"
        />
      </Face>
      <Cylinder x={186} y={103} z={32} r={10} h={16} open />
      <Face x={212} y={92} z={6}>
        <path d="M0 0 5 66" stroke={pigment.pale} strokeWidth="3" />
        <path
          d="M-10 0h22"
          stroke={pigment.side}
          strokeWidth="9"
          strokeLinecap="round"
        />
      </Face>
    </g>
  );
}

const scenes = {
  maintenance: {
    illustration: Maintenance,
    label: "Equipment maintenance: a motor, repair tools and a tool chest",
    hi: "उपकरण रखरखाव: मोटर, मरम्मत के औज़ार और टूल बॉक्स",
  },
  warehousing: {
    illustration: Warehousing,
    label: "Warehousing: stocked storage racks, pallets and a forklift",
    hi: "भंडारण: सामान से भरी अलमारियाँ, पैलेट और फोर्कलिफ्ट",
  },
  quality: {
    illustration: Quality,
    label:
      "Quality assurance: a microscope, sample tubes and an inspection checklist",
    hi: "गुणवत्ता आश्वासन: माइक्रोस्कोप, नमूने और निरीक्षण सूची",
  },
  food: {
    illustration: Food,
    label:
      "Food processing: a mixing vat, prepared food trays and a thermometer",
    hi: "खाद्य प्रसंस्करण: मिक्सिंग टैंक, तैयार भोजन की ट्रे और थर्मामीटर",
  },
  construction: {
    illustration: Construction,
    label: "Construction: a tower crane, building frame and safety cones",
    hi: "निर्माण: टावर क्रेन, इमारत का ढाँचा और सुरक्षा कोन",
  },
  healthcare: {
    illustration: Healthcare,
    label: "Healthcare: a prepared hospital bed, IV stand and patient monitor",
    hi: "स्वास्थ्य सेवा: तैयार अस्पताल का बिस्तर, आईवी स्टैंड और मॉनिटर",
  },
  facility: {
    illustration: Facility,
    label:
      "Facility management: a building, ventilation equipment and a service cart",
    hi: "सुविधा प्रबंधन: इमारत, वेंटिलेशन उपकरण और सर्विस ट्रॉली",
  },
} satisfies Record<
  Exclude<Industry, "manufacturing">,
  { illustration: () => ReactNode; label: string; hi: string }
>;

export function IndustryScene({ industry }: { industry: Industry }) {
  const { t } = usePreferences();
  const id = useId();
  if (industry === "manufacturing") return <FactoryScene />;
  const { illustration: Scene, label, hi } = scenes[industry];
  return (
    <svg
      className="factory-scene"
      viewBox="0 0 480 310"
      role="img"
      aria-label={t(label, hi)}
    >
      <defs>
        <linearGradient
          id={`${id}-platform`}
          x1="0%"
          y1="0%"
          x2="70%"
          y2="100%"
        >
          <stop stopColor="#c2a8ed" />
          <stop offset=".6" stopColor="#b098df" />
          <stop offset="1" stopColor="#a18bc9" />
        </linearGradient>
        <linearGradient id={`${id}-edge`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop stopColor="#ad96c4" />
          <stop offset="1" stopColor="#796586" />
        </linearGradient>
        <filter
          id={`${id}-shadow`}
          x="-30%"
          y="-30%"
          width="160%"
          height="180%"
        >
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      <ellipse
        cx="247"
        cy="275"
        rx="146"
        ry="18"
        fill="#171321"
        opacity=".2"
        filter={`url(#${id}-shadow)`}
      />
      <path d="m76 193 90-82 244 82-90 82z" fill={`url(#${id}-platform)`} />
      <path d="m76 193 244 82v19L76 207z" fill={`url(#${id}-edge)`} />
      <path d="m320 275 90-82v14l-90 87z" fill="#766288" />
      <path
        d="m80 195 240 81 86-79"
        fill="none"
        stroke="#c7b1dc"
        strokeWidth="3"
        opacity=".6"
      />
      <path
        d="m80 204 240 82 85-82"
        fill="none"
        stroke="#9e87b2"
        strokeWidth="4"
        opacity=".6"
      />
      <Scene />
    </svg>
  );
}
